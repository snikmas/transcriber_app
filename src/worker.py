from __future__ import annotations

import logging
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from src.analysis.statuses import AnalysisStatus, TranscriptionStatus
from src.database.database import JobRepository
from src.jobs import canonical_upload_directory, utc_now
from src.transcriber import TranscriptionEngine


class TranscriptionWorker:
    def __init__(
        self,
        repository: JobRepository,
        job_queue: Queue[str],
        engine: TranscriptionEngine,
        analysis_queue: Queue[str] | None = None,
        analysis_engine: Any | None = None,
        analysis_factory: Callable[[dict[str, Any], dict[str, Any]], Any] | None = None,
        upload_root: Path | None = None,
    ):
        self.repository = repository
        self.job_queue = job_queue
        self.engine = engine
        self.analysis_queue = analysis_queue
        self.analysis_engine = analysis_engine
        self.analysis_factory = analysis_factory
        self.upload_root = Path(upload_root) if upload_root is not None else None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self.run,
            name="transcription-worker",
            daemon=True,
        )
        self._thread.start()

    def run(self) -> None:
        while True:
            # Poll both stages so an analysis request cannot be starved by an
            # idle transcription queue (or vice versa).  Queues carry only the
            # durable job id; credentials and prompts never cross this boundary.
            job_id: str | None = None
            queue: Queue[str] = self.job_queue
            try:
                job_id = self.job_queue.get(timeout=0.1)
            except Empty:
                if self.analysis_queue is None:
                    continue
                try:
                    job_id = self.analysis_queue.get(timeout=0.1)
                    queue = self.analysis_queue
                    self.process_analysis(job_id)
                except Empty:
                    continue
                finally:
                    if job_id is not None:
                        queue.task_done()
                continue
            try:
                self.process(job_id)
            finally:
                self.job_queue.task_done()

    def process(self, job_id: str) -> None:
        job = self.repository.get(job_id)
        if not job:
            return
        input_path = Path(job["input_path"])
        try:
            self.repository.update_transcription(
                job_id,
                status=TranscriptionStatus.PROCESSING,
                updated_at=utc_now(),
            )
            result = self.engine.transcribe(input_path, job["filename"])
            self.repository.update_transcription(
                job_id,
                status=TranscriptionStatus.COMPLETED,
                updated_at=utc_now(),
                result=result,
            )
        except Exception as exc:
            logging.exception("Transcription job %s failed", job_id)
            self.repository.update_transcription(
                job_id,
                status=TranscriptionStatus.FAILED,
                updated_at=utc_now(),
                error=str(exc)[:500],
            )
        finally:
            # Only remove the per-job upload directory created by the API.
            # Legacy databases can contain arbitrary input paths (for
            # example ``/tmp/meeting.wav``); deleting their parent would turn
            # a normal worker completion into broad data loss.
            if self.upload_root is not None:
                upload_directory = canonical_upload_directory(self.upload_root, input_path, job_id)
                if upload_directory is not None:
                    shutil.rmtree(upload_directory, ignore_errors=True)

    def process_analysis(
        self,
        job_id: str,
        analyzer: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        """Run one persisted analysis stage while retaining the transcript on failure."""
        job = self.repository.get(job_id)
        analysis = self.repository.get_analysis(job_id)
        if job is None or analysis is None or job["transcription_status"] != "completed":
            return
        try:
            self.repository.update_analysis(
                job_id,
                status=AnalysisStatus.PROCESSING,
                updated_at=utc_now(),
            )
            callback = analyzer
            if callback is None and self.analysis_factory is not None:
                callback = self.analysis_factory(job, analysis)
            if callback is None and self.analysis_engine is not None:
                callback = self.analysis_engine.analyze
            if callback is None:
                raise RuntimeError("No analysis engine configured")
            result = callback(job["result"], analysis)
            if hasattr(result, "model_dump"):
                result = result.model_dump(mode="json")
            metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
            actual_model = metadata.get("actual_model") if isinstance(metadata, dict) else None
            chunk_count = metadata.get("chunk_count") if isinstance(metadata, dict) else None
            updates: dict[str, Any] = {}
            if isinstance(actual_model, str):
                updates["actual_model"] = actual_model
            if isinstance(chunk_count, int) and not isinstance(chunk_count, bool):
                updates["chunk_count"] = chunk_count
            self.repository.update_analysis(
                job_id,
                status=AnalysisStatus.COMPLETED,
                updated_at=utc_now(),
                result=result,
                error=None,
                **updates,
            )
        except Exception as exc:
            # Provider exceptions can contain response-shaped details.  Keep
            # logs as opaque lifecycle signals; persistence applies its own
            # allowlist and never stores this exception text.
            logging.error("Analysis job %s failed (%s)", job_id, type(exc).__name__)
            self.repository.update_analysis(
                job_id,
                status=AnalysisStatus.FAILED,
                updated_at=utc_now(),
                error=str(exc)[:500],
            )
