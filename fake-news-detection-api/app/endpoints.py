from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends, BackgroundTasks
from pydantic import BaseModel, Field
import uuid
import shutil
import os

from app.deps import get_current_user
from app.llm_manager import LLMManager
from app.serp_agent import SerpAgent
from app.classification_service import ClassificationService
from app.benchmark_service import BenchmarkService
from firebase_admin import firestore
from app.firebase import db

# --- Instantiate core components ---
llm = LLMManager()
serp = SerpAgent()
classifier = ClassificationService(llm, serp)

benchmarker = BenchmarkService(classifier, db)

router = APIRouter()

class PostData(BaseModel):
    post: str
    use_external_info: bool = True
    prompt_variant: str = "default"
    output_type: str = "score"
    iterations: int = Field(1, ge=1)

@router.post("/classify", dependencies=[Depends(get_current_user)])
async def classify_post(data: PostData):
    # 1) Query extrahieren
    try:
        query = classifier.extract_query(data.post)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2) Optional Artikel abrufen
    try:
        articles = classifier.fetch_articles(query, data.post, data.use_external_info)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"External info failed: {e}")

    # 3) Nachrichten an LLM bauen & Klassifikation durchführen
    msgs = classifier.build_messages(
        text=data.post,
        articles=articles,
        use_external=data.use_external_info,
        variant=data.prompt_variant,
        output=data.output_type,
    )

    try:
        responses = classifier.classify(msgs, data.iterations)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Classification failed: {e}")

    return {
        "search_query":        query,
        "used_prompt_variant": data.prompt_variant,
        "external_info_used":  data.use_external_info,
        "output_type":         data.output_type,
        "iterations":          data.iterations,
        "responses":           responses,
    }

@router.post("/benchmark", dependencies=[Depends(get_current_user)])
async def benchmark_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    use_external_info: bool = Form(True),
    prompt_variant: str = Form("default"),
    output_type: str = Form("binary"),
    iterations: int = Form(1, ge=1),
):
    # Temporäre CSV speichern
    job_id = str(uuid.uuid4())
    tmp_path = f"/tmp/benchmark_{job_id}.csv"
    with open(tmp_path, "wb") as out_f:
        shutil.copyfileobj(file.file, out_f)

    # Hintergrund-Job planen
    background_tasks.add_task(
        benchmarker.run,
        tmp_path,
        use_external_info,
        prompt_variant,
        output_type,
        iterations,
        job_id,
    )

    return {
        "job_id":  job_id,
        "message": "Benchmark started successfully — I'll keep running it even if you close the UI.",
    }

@router.get("/benchmarks", dependencies=[Depends(get_current_user)])
async def list_benchmarks(limit: int = 20):
    col    = db.collection("benchmarks")
    query  = col.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
    snaps  = query.stream()
    items  = []

    for snap in snaps:
        data = snap.to_dict() or {}
        ts   = data.get("timestamp")
        ts_str = getattr(ts, "isoformat", lambda: str(ts))()
        items.append({
            "id":        snap.id,
            "timestamp": ts_str,
            "params":    data.get("params"),
        })

    return items

@router.get("/benchmark/{benchmark_id}", dependencies=[Depends(get_current_user)])
async def get_benchmark(benchmark_id: str):
    doc_ref = db.collection("benchmarks").document(benchmark_id)
    snap    = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    saved  = snap.to_dict() or {}
    metrics = saved.get("metrics", {})
    params  = saved.get("params", {})

    results = [r.to_dict() for r in doc_ref.collection("results").stream()]

    return {
        **metrics,
        **params,
        "results": results,
        "id":      benchmark_id,
    }
