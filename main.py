from __future__ import annotations

import json
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Queue
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from src.analysis.providers import ProviderError, provider_from_config
from src.analysis.service import MeetingAnalysisService
from src.config import Settings, load_settings, provider_key, validate_live_analysis
from src.constants import SUPPORTED_CONTENT_TYPES, SUPPORTED_SUFFIXES
from src.database.database import JobRepository
from src.exports import (
    combined_json,
    meeting_notes_markdown,
    transcript_json,
    transcript_markdown,
    transcript_srt,
    transcript_txt,
)
from src.jobs import JobService, canonical_upload_directory, utc_now
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
    transcription_status: str
    analysis_status: str
    result: dict | None
    error: str | None
    transcription_error: str | None = None
    analysis: AnalysisResponse | None = None


class AnalysisResponse(BaseModel):
    """Public analysis lifecycle; internal paths and provider payloads are excluded."""

    analysis_id: str
    job_id: str
    status: str
    profile: str
    provider_id: str
    protocol: str
    requested_model: str
    actual_model: str | None
    output_language: str
    prompt_version: str
    schema_version: str
    chunk_count: int
    created_at: str
    updated_at: str
    result: dict | None
    error: str | None


JobResponse.model_rebuild()


class AnalysisRequest(BaseModel):
    """Optional provider settings; credentials are resolved only on the API server."""

    provider: str | None = None
    model: str | None = None
    output_language: str | None = None
    base_url: str | None = None


class ProviderTestResponse(BaseModel):
    """Client-safe result of a one-time provider readiness check."""

    status: str
    category: str
    provider_id: str
    protocol: str
    model: str
    actual_model: str | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    status: str
    mode: str
    model: str
    model_readiness: str
    max_upload_mb: int
    analysis_mode: str
    analysis_provider: str
    analysis_protocol: str
    analysis_readiness: str
    analysis_configured: bool


def public_analysis(analysis: dict | None) -> dict | None:
    if analysis is None:
        return None
    return {
        key: value
        for key, value in analysis.items()
        if key not in {"input_path", "prompt", "raw_provider_payload", "lease_id"}
    }


def public_job(job: dict, analysis: dict | None = None) -> dict:
    result = {key: value for key, value in job.items() if key != "input_path"}
    result["analysis"] = public_analysis(analysis)
    return result


def safe_filename(filename: str | None) -> str:
    name = Path(filename or "upload").name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return cleaned[:120] or "upload"


def owned_upload_directory(settings: Settings, input_path: str | None, job_id: str) -> Path | None:
    """Return an upload directory only when it is beneath this app's upload root.

    Jobs imported from an older database may contain arbitrary input paths.  A
    delete request must never interpret such a path as permission to remove
    its parent (for example ``/tmp``).
    """

    return canonical_upload_directory(settings.upload_dir, input_path, job_id)


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


def _analysis_service(
    settings: Settings, request: AnalysisRequest | None = None
) -> tuple[MeetingAnalysisService, dict[str, str]]:
    request = request or AnalysisRequest()
    provider_name = (request.provider or settings.analysis_provider).strip().lower()
    model = (request.model or settings.analysis_model).strip()
    output_language = (
        request.output_language or settings.analysis_output_language
    ).strip() or "auto"
    key = provider_key(settings, provider_name)
    mode = settings.analysis_mode.strip().lower()
    if provider_name == "demo":
        key = key or "demo"
    if not key:
        raise ValueError("provider_key_missing")
    if not model:
        raise ValueError("analysis_model_missing")
    if mode == "live":
        # This validates the environment-controlled limits and the configured
        # key without ever putting the key into a job or response.
        validate_live_analysis(settings, provider=provider_name)
    provider = provider_from_config(
        provider_name,
        api_key=key,
        model=model,
        base_url=request.base_url or settings.analysis_base_url,
        allow_local_urls=settings.allow_local_provider_urls,
    )
    service = MeetingAnalysisService(
        provider,
        model=model,
        output_language=output_language,
        max_attempts=settings.analysis_max_attempts,
        chunk_chars=settings.analysis_chunk_chars,
        max_chunks=settings.analysis_max_chunks,
        max_transcript_chars=settings.analysis_max_transcript_chars,
        timeout_seconds=settings.analysis_timeout_seconds,
    )
    metadata = {
        "provider_id": provider.provider_id,
        "protocol": str(
            provider.protocol.value if hasattr(provider.protocol, "value") else provider.protocol
        ),
        "requested_model": model,
        "output_language": output_language,
        "prompt_version": "meeting_v1",
        "schema_version": "1",
    }
    return service, metadata


def _analysis_callback(service: MeetingAnalysisService, job: dict, _analysis: dict):
    result = job.get("result") or {}
    segments = result.get("segments") if isinstance(result, dict) else None
    if not isinstance(segments, list):
        raise ValueError("analysis transcript is missing")
    duration = result.get("duration_seconds") if isinstance(result, dict) else None
    return service.analyze(segments, duration_seconds=duration)


_PROVIDER_TEST_CATEGORIES = frozenset(
    {
        "ok",
        "auth_failed",
        "model_not_found",
        "rate_limited",
        "credits_exhausted",
        "timeout",
        "protocol_mismatch",
        "unsafe_url",
        "provider_unavailable",
        "invalid_response",
    }
)


def _protocol_value(provider: object) -> str:
    protocol = getattr(provider, "protocol", "unknown")
    return str(protocol.value if hasattr(protocol, "value") else protocol)


def _provider_test_message(error: ProviderError) -> str:
    """Return only the stable, redacted provider error text."""

    messages = {
        "auth_failed": "Provider authentication failed.",
        "credits_exhausted": "Provider credits are exhausted.",
        "model_not_found": "The requested provider model was not found.",
        "rate_limited": "Provider rate limit reached; try again later.",
        "timeout": "Provider request timed out.",
        "protocol_mismatch": "Provider response did not match the selected protocol.",
        "provider_unavailable": "Provider is temporarily unavailable.",
        "invalid_response": "Provider returned an invalid response.",
        "unsafe_url": "Provider URL is not allowed.",
    }
    return messages.get(error.code, "Provider request failed.")


class _AnalysisEngineAdapter:
    def __init__(self, service: MeetingAnalysisService):
        self.service = service

    def analyze(self, job_result: dict, _analysis: dict):
        segments = job_result.get("segments") if isinstance(job_result, dict) else None
        if not isinstance(segments, list):
            raise ValueError("analysis transcript is missing")
        return self.service.analyze(
            segments,
            duration_seconds=job_result.get("duration_seconds"),
        )


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
        analysis_queue: Queue[str] = Queue()
        engine = TranscriptionEngine(app_settings)
        service = JobService(repository, job_queue, analysis_queue)
        worker = TranscriptionWorker(
            repository,
            job_queue,
            engine,
            analysis_queue,
            upload_root=app_settings.upload_dir,
        )
        app.state.analysis_services = {}
        try:
            default_analysis_service, _ = _analysis_service(app_settings)
        except (ProviderError, ValueError):
            try:
                default_analysis_service, _ = _analysis_service(
                    app_settings, AnalysisRequest(provider="demo")
                )
            except (ProviderError, ValueError):
                default_analysis_service = None
        if default_analysis_service is not None:
            worker.analysis_engine = _AnalysisEngineAdapter(default_analysis_service)

        def analysis_factory(job: dict, analysis: dict):
            configured = app.state.analysis_services.get(job["job_id"])
            if configured is None:
                return None

            def callback(_job_result: dict, metadata: dict):
                try:
                    return _analysis_callback(configured, job, metadata)
                finally:
                    app.state.analysis_services.pop(job["job_id"], None)

            return callback

        worker.analysis_factory = analysis_factory
        worker.start()

        app.state.settings = app_settings
        app.state.repository = repository
        app.state.job_service = service
        app.state.engine = engine
        app.state.worker = worker
        yield

    app = FastAPI(
        title="Meeting Notes & Action Tracker",
        version="1.0.0",
        description=(
            "Turn a meeting recording into timestamped text, structured notes, "
            "decisions, and action items. Demo mode is deterministic and clearly labeled."
        ),
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> dict:
        engine: TranscriptionEngine = request.app.state.engine
        current_settings: Settings = request.app.state.settings
        analysis_mode = current_settings.analysis_mode.strip().lower()
        analysis_configured = bool(
            current_settings.analysis_provider.strip()
            and current_settings.analysis_protocol.strip()
            and current_settings.analysis_model.strip()
        )
        if analysis_mode == "demo":
            analysis_readiness = "demo-ready"
        elif analysis_mode == "live" and analysis_configured:
            # Health is deliberately configuration-only: it does not inspect
            # credentials or call a provider just to report readiness.
            analysis_readiness = "configured"
        else:
            analysis_readiness = "not-configured"
        return {
            "status": "ok",
            "mode": current_settings.mode,
            "model": current_settings.model_name,
            "model_readiness": engine.readiness,
            "max_upload_mb": current_settings.max_upload_mb,
            "analysis_mode": analysis_mode,
            "analysis_provider": current_settings.analysis_provider,
            "analysis_protocol": current_settings.analysis_protocol,
            "analysis_readiness": analysis_readiness,
            "analysis_configured": analysis_configured,
        }

    @app.post("/providers/test", response_model=ProviderTestResponse)
    async def test_provider(
        request: Request, payload: AnalysisRequest | None = None
    ) -> dict[str, object]:
        """Run one bounded, one-time provider check without persisting a key or prompt.

        A successful check returns ``category=ok``.  Provider/network failures are
        represented as safe categories in a normal 200 response so the UI can show
        actionable feedback.  Invalid local configuration is a 422 and never makes
        a provider request.
        """

        payload = payload or AnalysisRequest()
        settings: Settings = request.app.state.settings
        provider_name = (payload.provider or settings.analysis_provider).strip().lower()
        model = (payload.model or settings.analysis_model).strip()
        analysis_mode = settings.analysis_mode.strip().lower()
        if analysis_mode not in {"demo", "live"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "analysis_mode_invalid",
                    "category": "invalid_response",
                    "message": "Analysis mode must be demo or live.",
                },
            )
        if not model:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "analysis_model_missing",
                    "category": "invalid_response",
                    "message": "An analysis model is required.",
                },
            )
        key = provider_key(settings, provider_name)
        if provider_name == "demo":
            key = key or "demo"
        elif not key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "provider_key_missing",
                    "category": "auth_failed",
                    "message": "A provider key is required for this connection test.",
                },
            )

        # Environment-controlled live limits are checked before any network call.
        if analysis_mode == "live":
            try:
                validate_live_analysis(settings, provider=provider_name)
            except ValueError as exc:
                code = str(exc)
                message = (
                    "A provider key is required for this connection test."
                    if code == "provider_key_missing"
                    else "Live analysis configuration is invalid."
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": code, "category": "auth_failed", "message": message},
                ) from None

        try:
            provider = provider_from_config(
                provider_name,
                api_key=key or "",
                model=model,
                base_url=payload.base_url or settings.analysis_base_url,
                allow_local_urls=settings.allow_local_provider_urls,
            )
        except ProviderError as exc:
            if exc.code in {"unsafe_url", "auth_failed"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": exc.code,
                        "category": exc.code,
                        "message": _provider_test_message(exc),
                    },
                ) from None
            return {
                "status": "error",
                "category": (
                    exc.code if exc.code in _PROVIDER_TEST_CATEGORIES else "invalid_response"
                ),
                "provider_id": provider_name,
                "protocol": "unknown",
                "model": model,
                "message": _provider_test_message(exc),
            }
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "invalid_provider_configuration",
                    "category": "invalid_response",
                    "message": "Provider configuration is invalid.",
                },
            ) from None

        provider_id = str(getattr(provider, "provider_id", provider_name))
        protocol = _protocol_value(provider)
        try:
            result = provider.generate(
                [
                    {
                        "role": "user",
                        "content": (
                            "Connection test. Return one minimal JSON object with a "
                            "summary field and no other content."
                        ),
                    }
                ],
                model=model,
                timeout=min(float(settings.analysis_timeout_seconds), 30.0),
            )
            structured = getattr(result, "structured", None)
            text_result = getattr(result, "text", None)
            if structured is None and isinstance(text_result, str):
                try:
                    structured = json.loads(text_result)
                except (TypeError, ValueError, json.JSONDecodeError):
                    structured = None
            if not isinstance(structured, dict):
                return {
                    "status": "error",
                    "category": "protocol_mismatch",
                    "provider_id": provider_id,
                    "protocol": protocol,
                    "model": model,
                    "actual_model": getattr(result, "actual_model", None),
                    "message": "Provider returned an invalid connection-test response.",
                }
            return {
                "status": "ok",
                "category": "ok",
                "provider_id": provider_id,
                "protocol": protocol,
                "model": model,
                "actual_model": getattr(result, "actual_model", None),
                "message": "Connection test succeeded.",
            }
        except ProviderError as exc:
            category = exc.code if exc.code in _PROVIDER_TEST_CATEGORIES else "provider_unavailable"
            return {
                "status": "error",
                "category": category,
                "provider_id": provider_id,
                "protocol": protocol,
                "model": model,
                "message": _provider_test_message(exc),
            }
        except Exception:
            # Do not echo arbitrary provider exceptions: they can contain request
            # bodies, credentials, or full prompts.
            return {
                "status": "error",
                "category": "provider_unavailable",
                "provider_id": provider_id,
                "protocol": protocol,
                "model": model,
                "message": "Provider is temporarily unavailable.",
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
        return public_job(job, request.app.state.repository.get_analysis(job_id))

    @app.get("/jobs", response_model=list[JobResponse])
    async def list_jobs(request: Request, limit: int = 20) -> list[dict]:
        safe_limit = max(1, min(limit, 100))
        return [
            public_job(job, request.app.state.repository.get_analysis(job["job_id"]))
            for job in request.app.state.repository.list(limit=safe_limit)
        ]

    @app.get("/jobs/{job_id}", response_model=JobResponse)
    async def get_job(job_id: str, request: Request) -> dict:
        # Keep the canonical jobs route byte-for-byte compatible with the
        # original transcription status route, including its stable 404.
        return await get_transcription(job_id, request)

    @app.get("/jobs/{job_id}/export")
    async def export_job(
        job_id: str,
        request: Request,
        format: str = Query(..., description="Export format, for example combined_json or srt"),
    ) -> Response:
        """Generate an allow-listed UTF-8 download from a completed transcript."""

        job = request.app.state.repository.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "job_not_found", "message": "Job not found."},
            )
        result = job.get("result")
        if not isinstance(result, dict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "transcript_not_ready",
                    "message": "Export requires a completed transcript.",
                },
            )

        # Keep both descriptive names and short aliases stable for API clients.
        format_key = format.strip().lower().replace("-", "_")
        public = public_job(job, request.app.state.repository.get_analysis(job_id))
        serializers = {
            "combined_json": (lambda: combined_json(public), "application/json", "combined.json"),
            "json": (lambda: transcript_json(result), "application/json", "transcript.json"),
            "transcript_json": (
                lambda: transcript_json(result),
                "application/json",
                "transcript.json",
            ),
            "meeting_notes_markdown": (
                lambda: meeting_notes_markdown(public),
                "text/markdown",
                "meeting-notes.md",
            ),
            "notes": (
                lambda: meeting_notes_markdown(public),
                "text/markdown",
                "meeting-notes.md",
            ),
            "transcript_markdown": (
                lambda: transcript_markdown(result),
                "text/markdown",
                "transcript.md",
            ),
            "markdown": (lambda: transcript_markdown(result), "text/markdown", "transcript.md"),
            "transcript_txt": (lambda: transcript_txt(result), "text/plain", "transcript.txt"),
            "txt": (lambda: transcript_txt(result), "text/plain", "transcript.txt"),
            "transcript_srt": (
                lambda: transcript_srt(result),
                "application/x-subrip",
                "transcript.srt",
            ),
            "srt": (lambda: transcript_srt(result), "application/x-subrip", "transcript.srt"),
        }
        serializer = serializers.get(format_key)
        if serializer is None:
            allowed = (
                "combined_json, meeting_notes_markdown, transcript_json, "
                "transcript_markdown, transcript_txt, transcript_srt"
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "unsupported_export_format",
                    "message": f"Unsupported export format. Choose one of: {allowed}.",
                },
            )
        body, media_type, suffix = serializer
        stem = safe_filename(str(result.get("filename") or job.get("filename") or "meeting"))
        stem = Path(stem).stem or "meeting"
        filename = f"{stem}-{suffix}" if suffix != "transcript.json" else f"{stem}.json"
        return Response(
            content=body(),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def _missing_job() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "job_not_found", "message": "Job not found."},
        )

    def _analysis_error(code: str, message: str, status_code: int = 400) -> HTTPException:
        return HTTPException(status_code=status_code, detail={"code": code, "message": message})

    async def _request_analysis(
        job_id: str,
        request: Request,
        payload: AnalysisRequest | None = None,
        *,
        retry: bool = False,
    ) -> dict:
        repository: JobRepository = request.app.state.repository
        job = repository.get(job_id)
        if job is None:
            raise _missing_job()
        if job["transcription_status"] != "completed":
            raise _analysis_error(
                "transcription_not_ready",
                "Analysis requires a completed transcript.",
                status.HTTP_409_CONFLICT,
            )
        existing = repository.get_analysis(job_id)
        if existing is not None and not retry:
            # A duplicate POST observes the same durable record and never
            # replaces an in-flight provider service or enqueues a second job.
            return public_analysis(existing) or {}
        payload = payload or AnalysisRequest()
        is_default = not any(
            value is not None
            for value in (
                payload.provider,
                payload.model,
                payload.output_language,
                payload.base_url,
            )
        )
        analysis_service = None
        metadata: dict[str, str]
        if is_default and request.app.state.worker.analysis_engine is not None:
            settings = request.app.state.settings
            metadata = {
                "provider_id": settings.analysis_provider,
                "protocol": settings.analysis_protocol,
                "requested_model": settings.analysis_model,
                "output_language": settings.analysis_output_language,
                "prompt_version": "meeting_v1",
                "schema_version": "1",
            }
        else:
            try:
                analysis_service, metadata = _analysis_service(request.app.state.settings, payload)
            except (ProviderError, ValueError) as exc:
                # ProviderError intentionally has a stable, redacted message.
                code = exc.code if isinstance(exc, ProviderError) else str(exc)
                messages = {
                    "provider_key_missing": "A provider key is required for live analysis.",
                    "analysis_model_missing": "An analysis model is required.",
                }
                raise _analysis_error(code, messages.get(code, str(exc))) from None
        if analysis_service is not None:
            request.app.state.analysis_services[job_id] = analysis_service
        try:
            if retry:
                analysis = request.app.state.job_service.retry_analysis(job_id, **metadata)
            else:
                analysis = request.app.state.job_service.request_analysis(job_id, **metadata)
        except (KeyError, ValueError) as exc:
            request.app.state.analysis_services.pop(job_id, None)
            message = (
                "Analysis requires a completed transcript."
                if isinstance(exc, ValueError)
                else "Job not found."
            )
            raise _analysis_error(
                "transcription_not_ready" if isinstance(exc, ValueError) else "job_not_found",
                message,
                status.HTTP_409_CONFLICT if isinstance(exc, ValueError) else 404,
            ) from None
        return public_analysis(analysis) or {}

    @app.post(
        "/transcribe/{job_id}/analysis",
        response_model=AnalysisResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def request_analysis(
        job_id: str, request: Request, payload: AnalysisRequest | None = None
    ) -> dict:
        return await _request_analysis(job_id, request, payload)

    @app.post(
        "/transcribe/{job_id}/analysis/retry",
        response_model=AnalysisResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def retry_analysis(
        job_id: str, request: Request, payload: AnalysisRequest | None = None
    ) -> dict:
        return await _request_analysis(job_id, request, payload, retry=True)

    @app.get("/transcribe/{job_id}/analysis", response_model=AnalysisResponse)
    async def get_analysis(job_id: str, request: Request) -> dict:
        if request.app.state.repository.get(job_id) is None:
            raise _missing_job()
        analysis = request.app.state.repository.get_analysis(job_id)
        if analysis is None:
            raise _analysis_error("analysis_not_requested", "Analysis has not been requested.", 404)
        return public_analysis(analysis) or {}

    # The jobs-prefixed aliases make the lifecycle discoverable for clients
    # that treat transcription as one job resource, while retaining the
    # original /transcribe routes unchanged.
    app.add_api_route(
        "/jobs/{job_id}/analysis",
        request_analysis,
        methods=["POST"],
        response_model=AnalysisResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    app.add_api_route(
        "/jobs/{job_id}/analysis/retry",
        retry_analysis,
        methods=["POST"],
        response_model=AnalysisResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    app.add_api_route(
        "/jobs/{job_id}/analysis",
        get_analysis,
        methods=["GET"],
        response_model=AnalysisResponse,
    )

    @app.delete("/jobs/{job_id}")
    async def delete_job(job_id: str, request: Request) -> dict:
        job = request.app.state.repository.get(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "job_not_found", "message": "Job not found."},
            )
        if job["transcription_status"] in {"queued", "processing"} or job["analysis_status"] in {
            "queued",
            "processing",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "job_active",
                    "message": "Wait for the job to finish before deleting it.",
                },
            )
        upload_directory = owned_upload_directory(
            request.app.state.settings, job.get("input_path"), job_id
        )
        if upload_directory is not None:
            shutil.rmtree(upload_directory, ignore_errors=True)
        request.app.state.repository.delete(job_id)
        return {"job_id": job_id, "deleted": True}

    return app


app = create_app()
