from __future__ import annotations

import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Queue
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict

from src.config import Settings, load_settings
from src.constants import SUPPORTED_CONTENT_TYPES, SUPPORTED_SUFFIXES
from src.database.database import JobRepository
from src.jobs import JobService, utc_now
from src.transcriber import TranscriptionEngine
from src.worker import TranscriptionWorker


class AcceptedJob(BaseModel):
    job_id: str
    status: str
    status_url: str


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str
    filename: str
    media_type: str
    status: str
    created_at: str
    updated_at: str
    result: dict | None
    error: str | None


class HealthResponse(BaseModel):
    status: str
    mode: str
    model: str
    model_readiness: str
    max_upload_mb: int


def public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key != "input_path"}


def safe_filename(filename: str | None) -> str:
    name = Path(filename or "upload").name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return cleaned[:120] or "upload"


async def save_upload(
    upload: UploadFile,
    *,
    settings: Settings,
    job_id: str,
) -> tuple[Path, str, str]:
    filename = safe_filename(upload.filename)
    suffix = Path(filename).suffix.lower()
    content_type = (upload.content_type or "application/octet-stream").lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_format",
                "message": f"Unsupported file extension: {suffix or 'none'}",
            },
        )
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_media_type",
                "message": f"Unsupported content type: {content_type}",
            },
        )

    job_dir = settings.upload_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    input_path = job_dir / f"input{suffix}"
    size = 0
    try:
        with input_path.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail={
                            "code": "file_too_large",
                            "message": (f"Upload exceeds the {settings.max_upload_mb} MB limit."),
                        },
                    )
                output.write(chunk)
        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "empty_file", "message": "The uploaded file is empty."},
            )
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    finally:
        await upload.close()
    return input_path, filename, content_type


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = JobRepository(app_settings.database_path)
        repository.initialize()
        repository.recover_incomplete(utc_now())
        if app_settings.upload_dir.exists():
            for child in app_settings.upload_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
        job_queue: Queue[str] = Queue()
        engine = TranscriptionEngine(app_settings)
        service = JobService(repository, job_queue)
        worker = TranscriptionWorker(repository, job_queue, engine)
        worker.start()

        app.state.settings = app_settings
        app.state.repository = repository
        app.state.job_service = service
        app.state.engine = engine
        yield

    app = FastAPI(
        title="Private Local Transcriber",
        version="1.0.0",
        description=(
            "Upload audio or video, process it asynchronously, and retrieve a "
            "timestamped transcript. Demo mode is deterministic and clearly labeled."
        ),
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> dict:
        engine: TranscriptionEngine = request.app.state.engine
        current_settings: Settings = request.app.state.settings
        return {
            "status": "ok",
            "mode": current_settings.mode,
            "model": current_settings.model_name,
            "model_readiness": engine.readiness,
            "max_upload_mb": current_settings.max_upload_mb,
        }

    @app.post(
        "/transcribe",
        response_model=AcceptedJob,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def transcribe(
        request: Request,
        file: Annotated[UploadFile, File()],
    ) -> dict:
        job_id = str(uuid4())
        input_path, filename, media_type = await save_upload(
            file,
            settings=request.app.state.settings,
            job_id=job_id,
        )
        try:
            job = request.app.state.job_service.create(
                job_id=job_id,
                filename=filename,
                media_type=media_type,
                input_path=input_path,
            )
        except Exception:
            shutil.rmtree(input_path.parent, ignore_errors=True)
            raise
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "status_url": f"/transcribe/{job['job_id']}",
        }

    @app.get("/transcribe/{job_id}", response_model=JobResponse)
    async def get_transcription(job_id: str, request: Request) -> dict:
        job = request.app.state.repository.get(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "job_not_found", "message": "Job not found."},
            )
        return public_job(job)

    @app.get("/jobs", response_model=list[JobResponse])
    async def list_jobs(request: Request, limit: int = 20) -> list[dict]:
        safe_limit = max(1, min(limit, 100))
        return [public_job(job) for job in request.app.state.repository.list(limit=safe_limit)]

    @app.delete("/jobs/{job_id}")
    async def delete_job(job_id: str, request: Request) -> dict:
        job = request.app.state.repository.get(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "job_not_found", "message": "Job not found."},
            )
        if job["status"] in {"queued", "processing"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "job_active",
                    "message": "Wait for the job to finish before deleting it.",
                },
            )
        input_path = job.get("input_path")
        if input_path:
            shutil.rmtree(Path(input_path).parent, ignore_errors=True)
        request.app.state.repository.delete(job_id)
        return {"job_id": job_id, "deleted": True}

    return app


app = create_app()
