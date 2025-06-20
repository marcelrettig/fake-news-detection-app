from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends
from app.deps import get_current_user
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score
from app.llm_manager import LLMManager
from app.serp_agent import SerpAgent
import json
import re
import logging
import os


# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, firestore

SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_CRED_PATH")
if not SERVICE_ACCOUNT_PATH:
    raise RuntimeError("Missing FIREBASE_CRED_PATH environment variable")

# Use a service account.
cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

# configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()
llm = LLMManager()
serp = SerpAgent()

class PostData(BaseModel):
    post: str
    use_external_info: bool = True
    prompt_variant: str = "default"
    output_type: str = "score"
    iterations: int = Field(1, ge=1)

@router.post("/classify", dependencies=[Depends(get_current_user)])
async def classify_post(data: PostData):
    if not data.post.strip():
        raise HTTPException(400, "Post must not be empty")

    # 1) Extract search query
    try:
        search_query = llm.extract_google_search_query(data.post)
    except Exception as e:
        raise HTTPException(502, f"Search-term extraction failed: {e}")

    # 2) Use your CrewAI agents to fetch summarized article block
    articles_block = ""
    if data.use_external_info:
        try:
            articles_block = serp.search_news(search_query, data.post) # <- uses the CrewAI workflow
            print("🔎 Retrieved articles block:", articles_block)
        except Exception as e:
            raise HTTPException(502, f"AI-powered article research failed: {e}")

    # 2) fetch articles once using google search
    #articles_block = ""
    #if data.use_external_info:
    #    google_search = GoogleSearchNews()
    #    try:
    #        articles_block = google_search.search_news(search_query)
    #        print(articles_block)
    #    except Exception as e:
    #        raise HTTPException(502, f"Article fetch failed: {e}")
    #    finally:
    #        google_search.close()

    # 2) fetch articles once using tagesschau
    #articles_block = ""
    #if data.use_external_info:
    #    outlet = NewsOutlet()
    #    try:
    #        links = outlet.search_articles(search_query)[:3]
    #        arts = outlet.load_articles(links)
    #        for idx, (link, texts) in enumerate(arts.items(), 1):
    #            articles_block += f"Article [{idx}]\nLink: {link}\nContent: {' '.join(texts)}\n\n"
    #    except Exception as e:
    #        raise HTTPException(502, f"Article fetch failed: {e}")
    #    finally:
    #        outlet.close()

    # 3) prepare the LLM messages once
    messages = llm.build_messages(
        post=data.post,
        articles_block=articles_block,
        use_external=data.use_external_info,
        prompt_variant=data.prompt_variant,
        output_type=data.output_type
    )

    # 4) run classification N times
    responses = []
    for _ in range(data.iterations):
        try:
            responses.append(llm.classify_once(messages))
        except Exception as e:
            raise HTTPException(502, f"LLM classification failed: {e}")

    return {
        "search_query":        search_query,
        "used_prompt_variant": data.prompt_variant,
        "external_info_used":  data.use_external_info,
        "output_type":         data.output_type,
        "iterations":          data.iterations,
        "responses":           responses
    }


@router.post("/benchmark", dependencies=[Depends(get_current_user)])
async def benchmark_csv(
    file: UploadFile = File(...),
    use_external_info: bool = Form(True),
    prompt_variant: str = Form("default"),
    output_type: str = Form("binary"),
    iterations: int = Form(1, ge=1),
):
    # (1) load & clean CSV
    try:
        df = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(400, f"Failed to read CSV: {e}")
    df = df.dropna(subset=['statement','label'], how='all')
    df = df[df['statement'].astype(str).str.strip() != ""]
    if 'statement' not in df.columns or 'label' not in df.columns:
        raise HTTPException(400, "CSV must contain 'statement' and 'label' columns")

    # (2) run benchmarks
    all_gold, all_pred, all_scores = [], [], []
    iter_correct = [0]*iterations
    iter_total   = [0]*iterations
    results = []

    for idx, row in df.iterrows():
        text = str(row['statement'])
        gold_bin = int(row['label']) >= 4

        # extract query
        try:
            query = llm.extract_google_search_query(text)
        except Exception as e:
            raise HTTPException(502, f"Row {idx}: search-term extraction failed: {e}")

        # fetch articles
        articles = ""
        if use_external_info:
            try:
                articles = serp.search_news(query, text)
            except Exception as e:
                raise HTTPException(502, f"Row {idx}: external-info fetch failed: {e}")

        msgs = llm.build_messages(
            post=text,
            articles_block=articles,
            use_external=use_external_info,
            prompt_variant=prompt_variant,
            output_type=output_type,
        )

        preds, scores, corrects = [], [], []
        for i in range(iterations):
            try:
                raw = llm.classify_once(msgs).strip()
            except Exception as e:
                raise HTTPException(502, f"Row {idx}, iter {i}: classification failed: {e}")

            # parse output
            pred_bin = False
            pred_sc  = None
            try:
                obj = json.loads(raw)
                if 'verdict' in obj:
                    pred_bin = obj['verdict'].strip().lower() == 'true'
                if 'score' in obj:
                    pred_sc  = float(obj['score'])
                    pred_bin = pred_sc >= 0.5
            except:
                low = raw.lower()
                if 'true' in low and 'false' not in low:
                    pred_bin = True
                elif 'false' in low and 'true' not in low:
                    pred_bin = False
                else:
                    m = re.search(r'\b0(?:\.\d+)?|1(?:\.0+)?\b', low)
                    if m:
                        pred_sc  = float(m.group(0))
                        pred_bin = pred_sc >= 0.5

            if pred_sc is None:
                pred_sc = 1.0 if pred_bin else 0.0

            is_corr = (pred_bin == gold_bin)
            preds.append(pred_bin)
            scores.append(pred_sc)
            corrects.append(is_corr)

            all_gold.append(gold_bin)
            all_pred.append(pred_bin)
            all_scores.append(pred_sc)
            iter_total[i]   += 1
            iter_correct[i] += int(is_corr)

        results.append({
            "statement":   text,
            "gold_binary": gold_bin,
            "predictions": preds,
            "scores":      scores,
            "correctness": corrects,
        })

    # (3) compute summary metrics
    cm_list = confusion_matrix(all_gold, all_pred).tolist()
    # flatten into a map
    summary_cm = {
        "TN": cm_list[0][0],
        "FP": cm_list[0][1],
        "FN": cm_list[1][0],
        "TP": cm_list[1][1],
    }
    precision = float(precision_score(all_gold, all_pred, zero_division=0))
    recall    = float(recall_score(all_gold, all_pred, zero_division=0))
    f1        = float(f1_score(all_gold, all_pred, zero_division=0))

    # histogram
    try:
        import numpy as np
        counts, edges = np.histogram(all_scores, bins=10, range=(0.0,1.0))
        hist = {"bin_edges": [float(x) for x in edges], "counts": [int(x) for x in counts]}
    except ImportError:
        bins = [i/10 for i in range(11)]
        cnts = [0]*10
        for sc in all_scores:
            idx = min(int(sc*10),9)
            cnts[idx] += 1
        hist = {"bin_edges": bins, "counts": cnts}

    iter_acc = [float(iter_correct[i]/iter_total[i]) if iter_total[i]>0 else 0.0
                for i in range(iterations)]
    total_preds   = len(all_gold)
    correct_preds = sum(int(g==p) for g,p in zip(all_gold, all_pred))
    overall_acc   = float(correct_preds/total_preds) if total_preds>0 else 0.0

    summary_metrics = {
        "accuracy":           overall_acc,
        "precision":          precision,
        "recall":             recall,
        "f1_score":           f1,
        "confusion_matrix":   summary_cm,
        "score_histogram":    hist,
        "iteration_accuracy": iter_acc,
        "total_predictions":  total_preds,
        "correct_predictions":correct_preds,
    }

    # (4) save to Firestore
    try:
        doc = db.collection("benchmarks").document()
        doc.set({
            "timestamp": firestore.SERVER_TIMESTAMP,
            "params": {
                "use_external_info": use_external_info,
                "prompt_variant": prompt_variant,
                "output_type": output_type,
                "iterations": iterations,
            },
            "metrics": summary_metrics,
        })
        # detailed results in subcollection
        batch = db.batch()
        for r in results:
            batch.set(doc.collection("results").document(), r)
        batch.commit()
        summary_metrics["id"] = doc.id
        logger.info(f"Saved benchmark {doc.id}")
    except Exception as e:
        logger.exception("Firestore save failed")
        raise HTTPException(500, f"Could not save benchmark: {e}")

    # (5) return
    return {
        **summary_metrics,
        "results_id":          doc.id,
        "results":             results,
        "used_prompt_variant": prompt_variant,
        "external_info_used":  use_external_info,
        "output_type":         output_type,
        "iterations":          iterations,
    }


@router.get("/benchmarks", dependencies=[Depends(get_current_user)])
async def list_benchmarks(limit: int = 20):
    col   = db.collection("benchmarks")
    query = col.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
    snapshots = query.stream()
    items = []
    for snap in snapshots:
        data = snap.to_dict() or {}
        ts   = data.get("timestamp")
        # convert Firestore Timestamp to ISO string
        try:
            ts_str = ts.isoformat()
        except Exception:
            try:
                ts_str = ts.to_rfc3339()
            except Exception:
                ts_str = str(ts)
        items.append({
            "id":        snap.id,
            "timestamp": ts_str,
            "params":    data.get("params"),
        })
    return items

@router.get("/benchmark/{benchmark_id}", dependencies=[Depends(get_current_user)])
async def get_benchmark(benchmark_id: str):
    doc_ref = db.collection("benchmarks").document(benchmark_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(404, "Benchmark not found")

    saved = snap.to_dict() or {}
    metrics = saved.get("metrics", {})
    params  = saved.get("params", {})

    # load detailed results subcollection
    results = []
    for r_snap in doc_ref.collection("results").stream():
        results.append(r_snap.to_dict())

    # merge: metrics (flat) + results + params
    return {
        **metrics,
        "results": results,
        **params,                     # now includes output_type, prompt_variant, etc.
        "id": benchmark_id,
    }