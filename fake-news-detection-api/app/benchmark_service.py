import os
import time
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score
from firebase_admin import firestore

from .classification_service import ClassificationService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class BenchmarkService:
    def __init__(self, classifier: ClassificationService, db_client):
        self.classifier = classifier
        self.db = db_client

    def _parse_output(self, raw: str) -> tuple[bool, float]:
        # Versucht zuerst JSON, fällt bei Fehlern auf Heuristik zurück
        try:
            obj = json.loads(raw)
            score = float(obj.get("score", 0.0))
            # Wenn überhaupt ein Score da ist, entscheidet der Schwellenwert
            if "score" in obj:
                return (score >= 0.5), score
            # Sonst (z.B. nur verdict-Feld) über das verdict-Feld
            verdict = obj.get("verdict","").strip().lower() == "true"
            return verdict, score
        except Exception:
            low = raw.lower()
            if "true" in low and "false" not in low:
                return True, 1.0
            if "false" in low and "true" not in low:
                return False, 0.0
            m = re.search(r"\b0(?:\.\d+)?|1(?:\.0+)?\b", low)
            if m:
                sc = float(m.group(0))
                return sc >= 0.5, sc
            return False, 0.0

    def _classify_row(self, idx, row, use_external, variant, output, iterations):
        text = str(row["statement"])
        gold = int(row["label"]) >= 4

        try:
            query = self.classifier.extract_query(text)
        except Exception as e:
            logger.error(f"Row {idx}: Query-Extraktion fehlgeschlagen: {e}")
            return None

        articles = self.classifier.fetch_articles(query, text, use_external)
        msgs = self.classifier.build_messages(text, articles, use_external, variant, output)

        preds, scores, corrects = [], [], []
        for i in range(iterations):
            try:
                raw = self.classifier.llm.classify_once(msgs).strip()
            except Exception as e:
                logger.error(f"Row {idx}, Iter {i}: Klassifikation fehlgeschlagen: {e}")
                continue

            pred, sc = self._parse_output(raw)
            preds.append(pred)
            scores.append(sc)
            corrects.append(pred == gold)

        return {
            "statement": text,
            "gold_binary": gold,
            "predictions": preds,
            "scores": scores,
            "correctness": corrects,
        }

    def _compute_metrics(self, results, iterations, output_type):
        # compute iteration-level accuracy
        iter_corr = [0] * iterations
        iter_tot  = [0] * iterations

        for r in results:
            for i, c in enumerate(r["correctness"]):
                iter_tot[i]  += 1
                iter_corr[i] += int(c)

        # build y_true / y_pred / all_scores exactly as the UI does
        if output_type in ("score", "detailed"):
            # one entry per individual score
            y_true     = [r["gold_binary"] for r in results for _ in r["scores"]]
            y_pred     = [s >= 0.5           for r in results for s in r["scores"]]
            all_scores = [s                  for r in results for s in r["scores"]]
        else:
            # binary: majority vote per statement
            y_true     = [r["gold_binary"] for r in results]
            y_pred     = [
                sum(r["predictions"]) > len(r["predictions"]) / 2
                for r in results
            ]
            # histogram still uses individual scores
            all_scores = [s for r in results for s in r["scores"]]

        try:
            # labels=[False, True] ensures row0=Actual False (Fake), row1=Actual True
            cm = confusion_matrix(y_true, y_pred, labels=[False, True])
            tp = int(cm[0, 0])  # Fake correctly identified as Fake
            fn = int(cm[0, 1])  # Fake misclassified as TrueNews
            fp = int(cm[1, 0])  # TrueNews misclassified as Fake
            tn = int(cm[1, 1])  # TrueNews correctly identified
        except Exception:
            tp = fn = fp = tn = 0

        precision = precision_score(y_true, y_pred, pos_label=False, zero_division=0)
        recall    = recall_score(y_true, y_pred, pos_label=False, zero_division=0)
        f1        = f1_score(y_true, y_pred, pos_label=False, zero_division=0)

        hist_counts, hist_edges = np.histogram(all_scores, bins=10, range=(0.0, 1.0))
        total = len(y_true)
        acc_overall = (
            sum(int(gt == pred) for gt, pred in zip(y_true, y_pred)) / total
            if total else 0.0
        )

        return {
            "accuracy":           acc_overall,
            "precision":          precision,
            "recall":             recall,
            "f1_score":           f1,
            "confusion_matrix":   {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
            "score_histogram":    {
                "bin_edges": hist_edges.tolist(),
                "counts":    hist_counts.tolist()
            },
            "iteration_accuracy": [
                (iter_corr[i] / iter_tot[i]) if iter_tot[i] else 0.0
                for i in range(iterations)
            ],
            "total_predictions":  total,
        }

    def _save_to_firestore(self, job_id, params, summary, results):
        doc = self.db.collection("benchmarks").document(job_id)
        doc.set({
            "timestamp": firestore.SERVER_TIMESTAMP,
            "params":    params,
            "metrics":   summary
        })
        batch = self.db.batch()
        for r in results:
            batch.set(doc.collection("results").document(), r)
        batch.commit()
        logger.info(f"Benchmark {job_id} gespeichert.")

    def run(
        self,
        csv_path: str,
        use_external: bool,
        variant: str,
        output: str,
        iterations: int,
        model: str,
        job_id: str
    ):
        start = time.time()
        self.classifier.llm.set_model(model)
        self.classifier.serp.set_model(model)

        logger.info(f"Starting benchmark {job_id} using LLM model '{model}'")
        self.classifier.llm.extract_model   = model
        self.classifier.llm.classify_model  = model
        self.classifier.serp.research_model = model
        self.classifier.serp.summary_model  = model

        df = pd.read_csv(csv_path).dropna(subset=["statement", "label"])
        df = df[df["statement"].astype(str).str.strip() != ""]
        if df.empty:
            logger.error("Keine gültigen Zeilen in CSV.")
            return

        model_params = {
            "extract_model":   self.classifier.llm.extract_model,
            "classify_model":  self.classifier.llm.classify_model,
            "research_model":  self.classifier.serp.research_model,
            "summary_model":   self.classifier.serp.summary_model,
            "selected_model":  model,
        }

        params = {
            **model_params,
            "use_external_info": use_external,
            "prompt_variant":    variant,
            "output_type":       output,
            "iterations":        iterations
        }

        with ThreadPoolExecutor(max_workers=min(32, len(df))) as exec:
            futures = {
                exec.submit(
                    self._classify_row,
                    idx, row,
                    use_external, variant, output, iterations
                ): idx
                for idx, row in df.iterrows()
            }
            results = [
                f.result()
                for f in as_completed(futures)
                if f.result() is not None
            ]

        # compute metrics using the UI‐aligned logic
        summary = self._compute_metrics(results, iterations, output)

        summary["duration_seconds"] = time.time() - start

        self._save_to_firestore(job_id, params, summary, results)

        try:
            os.remove(csv_path)
        except OSError:
            pass
