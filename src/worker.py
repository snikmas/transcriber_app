from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from queue import Queue

from src.constants import JobStatus
from src.database.database import JobRepository
from src.jobs import utc_now
from src.transcriber import TranscriptionEngine


class TranscriptionWorker:
    def __init__(
        self,
        repository: JobRepository,
        job_queue: Queue[str],
        engine: TranscriptionEngine,
    ):
        self.repository = repository
        self.job_queue = job_queue
        self.engine = engine
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
            job_id = self.job_queue.get()
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
            self.repository.update(
                job_id,
                status=JobStatus.PROCESSING,
                updated_at=utc_now(),
            )
            result = self.engine.transcribe(input_path, job["filename"])
            self.repository.update(
                job_id,
                status=JobStatus.COMPLETED,
                updated_at=utc_now(),
                result=result,
            )
        except Exception as exc:
            logging.exception("Transcription job %s failed", job_id)
            self.repository.update(
                job_id,
                status=JobStatus.FAILED,
                updated_at=utc_now(),
                error=str(exc)[:500],
            )
        finally:
            shutil.rmtree(input_path.parent, ignore_errors=True)
