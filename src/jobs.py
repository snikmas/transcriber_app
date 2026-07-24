from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from queue import Queue
from uuid import uuid4

from src.constants import JobStatus
from src.database.database import JobRepository


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class JobService:
    def __init__(self, repository: JobRepository, job_queue: Queue[str]):
        self.repository = repository
        self.job_queue = job_queue

    def create(
        self,
        *,
        filename: str,
        media_type: str,
        input_path: Path,
        job_id: str | None = None,
    ) -> dict:
        now = utc_now()
        job = {
            "job_id": job_id or str(uuid4()),
            "filename": filename,
            "media_type": media_type,
            "input_path": str(input_path),
            "status": JobStatus.QUEUED.value,
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": None,
        }
        self.repository.create(job)
        self.job_queue.put(job["job_id"])
        return job
