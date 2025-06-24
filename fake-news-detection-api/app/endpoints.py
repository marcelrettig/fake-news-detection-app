from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends, BackgroundTasks
from app.deps import get_current_user
from app.llm_manager import LLMManager
from app.serp_agent import SerpAgent
from pydantic import BaseModel, Field
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score
import pandas as pd
import numpy as np
import json
import re
import logging
import os
import uuid
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, firestore

SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_CRED_PATH")
if not SERVICE_ACCOUNT_PATH:
    raise RuntimeError("Missing FIREBASE_CRED_PATH environment variable")

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)
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

    # 2) Fetch external info if desired
    articles_block = ""
    if data.use_external_info:
        try:
            articles_block = serp.search_news(search_query, data.post)
            logger.info("🔎 Retrieved articles block")
        except Exception as e:
            raise HTTPException(502, f"AI-powered article research failed: {e}")

    # 3) Prepare the LLM messages
    messages = llm.build_messages(
        post=data.post,
        articles_block=articles_block,
        use_external=data.use_external_info,
        prompt_variant=data.prompt_variant,
        output_type=data.output_type
    )

    # 4) Run classification N times
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


def classify_row(idx, row, use_external_info, prompt_variant, output_type, iterations):
    text = str(row['statement'])
    gold_bin = int(row['label']) >= 4

    # extract query
    try:
        query = llm.extract_google_search_query(text)
    except Exception as e:
        logger.error(f"Row {idx}: search-term extraction failed: {e}")
        return None

    # fetch articles
    articles = ""
    if use_external_info:
        try:
            articles = serp.search_news(query, text)
        except Exception as e:
            logger.error(f"Row {idx}: external-info fetch failed: {e}")

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
            logger.error(f"Row {idx}, iter {i}: classification failed: {e}")
            continue

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

    return {
        "statement":   text,
        "gold_binary": gold_bin,
        "predictions": preds,
        "scores":      scores,
        "correctness": corrects,
    }


def run_benchmark_job(
    tmp_csv_path: str,
    use_external_info: bool,
    prompt_variant: str,
    output_type: str,
    iterations: int,
    job_id: str,
):
    start_time = time.time()

    # (1) load & clean CSV
    try:
        df = pd.read_csv(tmp_csv_path)
    except Exception as e:
        logger.error(f"Failed to read CSV {tmp_csv_path}: {e}")
        return

    df = df.dropna(subset=['statement','label'], how='all')
    df = df[df['statement'].astype(str).str.strip() != ""]
    if 'statement' not in df.columns or 'label' not in df.columns:
        logger.error("CSV missing required columns 'statement' or 'label'")
        return

    # (2) run benchmarks in parallel
    results = []
    max_workers = min(32, len(df))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(classify_row, idx, row, use_external_info, prompt_variant, output_type, iterations): idx
            for idx, row in df.iterrows()
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                res = fut.result()
                if res is not None:
                    results.append(res)
            except Exception as e:
                logger.error(f"Row {idx} failed: {e}")

    # (3) compute summary metrics
    all_gold, all_pred, all_scores = [], [], []
    iter_correct = [0] * iterations
    iter_total   = [0] * iterations

    for r in results:
        gold = r["gold_binary"]
        for i, (pred, sc, corr) in enumerate(zip(r["predictions"], r["scores"], r["correctness"])):
            all_gold.append(gold)
            all_pred.append(pred)
            all_scores.append(sc)
            iter_total[i]   += 1
            iter_correct[i] += int(corr)

    try:
        tn_np, fp_np, fn_np, tp_np = confusion_matrix(all_gold, all_pred).ravel()
        summary_cm = {"TN": int(tn_np), "FP": int(fp_np), "FN": int(fn_np), "TP": int(tp_np)}
    except Exception:
        summary_cm = {"TN": 0, "FP": 0, "FN": 0, "TP": 0}

    precision = float(precision_score(all_gold, all_pred, zero_division=0))
    recall    = float(recall_score(all_gold, all_pred, zero_division=0))
    f1        = float(f1_score(all_gold, all_pred, zero_division=0))

    try:
        counts, edges = np.histogram(all_scores, bins=10, range=(0.0, 1.0))
        hist = {"bin_edges": edges.tolist(), "counts": counts.tolist()}
    except Exception:
        bins = [i/10 for i in range(11)]
        cnts = [0]*10
        for sc in all_scores:
            idx = min(int(sc*10), 9)
            cnts[idx] += 1
        hist = {"bin_edges": bins, "counts": cnts}

    iter_acc = [
        float(iter_correct[i]) / int(iter_total[i]) if iter_total[i] > 0 else 0.0
        for i in range(iterations)
    ]
    total_preds   = int(len(all_gold))
    correct_preds = int(sum(1 for g,p in zip(all_gold, all_pred) if g == p))
    overall_acc   = float(correct_preds) / float(total_preds) if total_preds > 0 else 0.0

    end_time = time.time()
    duration = end_time - start_time

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
        "duration_seconds":   duration
    }

    model_params = {
        "extract_model":  llm.extract_model,
        "classify_model": llm.classify_model,
        "research_model": serp.research_model,
        "summary_model":  serp.summary_model,
    }

    # (4) save to Firestore
    try:
        doc = db.collection("benchmarks").document(job_id)
        doc.set({
            "timestamp": firestore.SERVER_TIMESTAMP,
            "params": {
                **model_params,
                "use_external_info": use_external_info,
                "prompt_variant":    prompt_variant,
                "output_type":       output_type,
                "iterations":        int(iterations),
            },
            "metrics": summary_metrics,
        })
        batch = db.batch()
        for r in results:
            batch.set(doc.collection("results").document(), r)
        batch.commit()
        logger.info(f"Saved benchmark {doc.id}")
    except Exception as e:
        logger.exception("Firestore save failed")

    # clean up
    try:
        os.remove(tmp_csv_path)
    except OSError:
        pass


@router.post("/benchmark", dependencies=[Depends(get_current_user)])
async def benchmark_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    use_external_info: bool = Form(True),
    prompt_variant: str = Form("default"),
    output_type: str = Form("binary"),
    iterations: int = Form(1, ge=1),
):
    # save the upload to a temp file
    job_id = str(uuid.uuid4())
    tmp_path = f"/tmp/benchmark_{job_id}.csv"
    with open(tmp_path, "wb") as out_f:
        shutil.copyfileobj(file.file, out_f)

    # schedule the background job
    background_tasks.add_task(
        run_benchmark_job,
        tmp_path,
        use_external_info,
        prompt_variant,
        output_type,
        iterations,
        job_id,
    )

    return {
        "job_id": job_id,
        "message": "Benchmark started successfully—I'll keep running it even if you close the UI."
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
        try:
            ts_str = ts.isoformat()
        except:
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

    results = []
    for r_snap in doc_ref.collection("results").stream():
        results.append(r_snap.to_dict())

    return {
        **metrics,
        "results": results,
        **params,
        "id": benchmark_id,
    }
