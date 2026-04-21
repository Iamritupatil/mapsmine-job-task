from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from scraper import GoogleMapsScraper
from utils import build_output_basename, setup_logger

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
PROXY_URL = os.environ.get("PROXY_URL")  # e.g. http://user:pass@host:port
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger = setup_logger()
executor = ThreadPoolExecutor(max_workers=2)
job_lock = Lock()


@dataclass
class JobState:
    job_id: str
    query: str
    limit: int
    headless: bool
    out_format: str
    workers: int = 1
    status: str = "queued"
    processed_listings: int = 0
    target: int = 0
    result_file: str | None = None
    row_count: int = 0
    error: str | None = None
    created_at: float = field(default_factory=time.time)


jobs: dict[str, JobState] = {}


class ScrapeRequest(BaseModel):
    query: str = Field(min_length=2)
    limit: int = Field(default=50, ge=1, le=500)
    headless: bool = True
    workers: int = Field(default=1, ge=1, le=1)
    format: str = Field(default="xlsx", pattern="^(xlsx|csv)$")


app = FastAPI(title="MapsMine Scraper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_job(job: JobState) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": {
            "processed_listings": job.processed_listings,
            "target": job.target,
        },
        "result_file": job.result_file,
        "row_count": job.row_count,
        "error": job.error,
    }


def update_job(job_id: str, **kwargs: Any) -> None:
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            return
        for key, value in kwargs.items():
            setattr(job, key, value)


def run_scrape_job(job_id: str) -> None:
    with job_lock:
        job = jobs.get(job_id)
    if not job:
        return

    output_basename = build_output_basename(job.query, job.limit)
    output_file = OUTPUT_DIR / f"{output_basename}.{job.out_format}"

    scraper = GoogleMapsScraper(
        query=job.query,
        limit=job.limit,
        headless=job.headless,
        output_path=str(output_file),
        workers=int(job.workers or 1),
        proxy=PROXY_URL,
    )

    def progress_callback(processed: int, target: int) -> None:
        update_job(job_id, processed_listings=processed, target=target, status="running")

    try:
        update_job(job_id, status="running", target=job.limit)
        rows = scraper.run(progress_callback=progress_callback)
        output_path = scraper.save_output()

        update_job(
            job_id,
            status="completed",
            processed_listings=len(rows),
            row_count=len(rows),
            result_file=str(output_path.relative_to(BASE_DIR)).replace("\\", "/"),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed: %s", job_id, exc)
        error_message = str(exc) or repr(exc)
        update_job(job_id, status="failed", error=error_message)
    finally:
        scraper.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scrape")
def create_scrape_job(payload: ScrapeRequest) -> dict[str, str]:
    job_id = str(uuid.uuid4())
    state = JobState(
        job_id=job_id,
        query=payload.query,
        limit=payload.limit,
        headless=payload.headless,
        out_format=payload.format,
        workers=payload.workers,
        target=payload.limit,
    )

    with job_lock:
        jobs[job_id] = state

    executor.submit(run_scrape_job, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/scrape/{job_id}")
def get_scrape_job(job_id: str) -> dict[str, Any]:
    with job_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_job(job)


@app.get("/scrape/{job_id}/download")
def download_scrape_result(job_id: str) -> FileResponse:
    with job_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.result_file:
        raise HTTPException(status_code=400, detail="Result is not ready")

    file_path = BASE_DIR / job.result_file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Result file missing")

    return FileResponse(path=file_path, filename=file_path.name)
