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

    def _compute_metrics(self, results, iterations):
        all_gold, all_pred, all_scores = [], [], []
        iter_corr = [0] * iterations
        iter_tot  = [0] * iterations

        for r in results:
            gold = r["gold_binary"]     # False = Fake, True = TrueNews
            for i, (p, s, c) in enumerate(zip(r["predictions"], r["scores"], r["correctness"])):
                all_gold.append(gold)
                all_pred.append(p)
                all_scores.append(s)
                iter_tot[i]  += 1
                iter_corr[i] += int(c)

        try:
            # labels=[False, True] sorgt dafür, dass Zeile 0 = Actual False = Fake,
            # Zeile 1 = Actual True = TrueNews ist.
            cm = confusion_matrix(all_gold, all_pred, labels=[False, True])
            # cm = [[TP_fake, FN_fake],
            #       [FP_true, TN_true]]
            tp = int(cm[0, 0])  # echte Fakes korrekt als Fake
            fn = int(cm[0, 1])  # echte Fakes fälschlich als TrueNews
            fp = int(cm[1, 0])  # echte TrueNews fälschlich als Fake
            tn = int(cm[1, 1])  # echte TrueNews korrekt als TrueNews
        except Exception:
            tp = fn = fp = tn = 0

        # Wir nehmen pos_label=False, weil False (= Fake) unsere positive Klasse ist.
        precision = precision_score(all_gold, all_pred, pos_label=False, zero_division=0)
        recall    = recall_score(all_gold, all_pred, pos_label=False, zero_division=0)
        f1        = f1_score(all_gold, all_pred, pos_label=False, zero_division=0)

        hist_counts, hist_edges = np.histogram(all_scores, bins=10, range=(0.0, 1.0))
        total = len(all_gold)
        acc_overall = sum(int(g == p) for g, p in zip(all_gold, all_pred)) / total if total else 0.0

        return {
            "accuracy":           acc_overall,
            "precision":          precision,
            "recall":             recall,
            "f1_score":           f1,
            "confusion_matrix":   {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
            "score_histogram":    {"bin_edges": hist_edges.tolist(), "counts": hist_counts.tolist()},
            "iteration_accuracy": [ (iter_corr[i] / iter_tot[i]) if iter_tot[i] else 0.0
                                    for i in range(iterations) ],
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

    def run(self, csv_path: str, use_external: bool, variant: str, output: str, iterations: int, job_id: str):
        start = time.time()
        df = pd.read_csv(csv_path).dropna(subset=["statement", "label"])
        df = df[df["statement"].astype(str).str.strip() != ""]
        if df.empty:
            logger.error("Keine gültigen Zeilen in CSV.")
            return

        # Modelle mit ins DB-Dokument
        model_params = {
            "extract_model":   self.classifier.llm.extract_model,
            "classify_model":  self.classifier.llm.classify_model,
            "research_model":  self.classifier.serp.research_model,
            "summary_model":   self.classifier.serp.summary_model,
        }
        params = {
            **model_params,
            "use_external_info": use_external,
            "prompt_variant":    variant,
            "output_type":       output,
            "iterations":        iterations
        }

        # Parallele Klassifikation
        with ThreadPoolExecutor(max_workers=min(32, len(df))) as exec:
            futures = {
                exec.submit(self._classify_row, idx, row, use_external, variant, output, iterations): idx
                for idx, row in df.iterrows()
            }
            results = [f.result() for f in as_completed(futures) if f.result() is not None]

        # Metriken berechnen
        summary = self._compute_metrics(results, iterations)

        # Dauer hinzufügen
        duration = time.time() - start
        summary["duration_seconds"] = duration

        # In Firestore speichern
        self._save_to_firestore(job_id, params, summary, results)

        try:
            os.remove(csv_path)
        except OSError:
            pass
