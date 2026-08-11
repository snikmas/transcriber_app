from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from queue import Queue
from uuid import uuid4

from src.analysis.statuses import AnalysisStatus
from src.constants import JobStatus
from src.database.database import JobRepository


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_upload_directory(
    upload_root: Path,
    input_path: str | Path | None,
    job_id: str,
) -> Path | None:
    """Return the owned upload directory for a job, or ``None`` for legacy paths.

    A database may contain paths written by an older application version.  The
    worker and API deletion path may only remove the exact canonical
    ``upload_root/job_id`` directory created by this application.  Resolving
    both paths also prevents a symlink or ``..`` component from widening the
    deletion target.
    """

    if not input_path:
        return None
    job_component = Path(job_id)
    if (
        not job_id
        or job_id in {".", ".."}
        or job_component.is_absolute()
        or job_component.name != job_id
        or len(job_component.parts) != 1
    ):
        return None

    try:
        root = Path(upload_root).resolve(strict=False)
        candidate = Path(input_path).parent
        resolved_candidate = candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return None

    expected = root / job_id
    if resolved_candidate != expected or candidate.is_symlink():
        return None
    return resolved_candidate


class JobService:
    def __init__(
        self,
        repository: JobRepository,
        job_queue: Queue[str],
        analysis_queue: Queue[str] | None = None,
    ):
        self.repository = repository
        self.job_queue = job_queue
        self.analysis_queue = analysis_queue or Queue()

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

    def request_analysis(self, job_id: str, **metadata: object) -> dict:
        """Queue analysis for an existing transcript without retranscribing it."""
        job = self.repository.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        if job["transcription_status"] != "completed":
            raise ValueError("Analysis requires a completed transcript")
        analysis, created = self.repository.create_analysis_if_absent(job_id, **metadata)
        if created and analysis["status"] in {
            AnalysisStatus.QUEUED.value,
            AnalysisStatus.PROCESSING.value,
        }:
            self.analysis_queue.put(job_id)
        return analysis

    def retry_analysis(self, job_id: str, **metadata: object) -> dict:
        """Reset a failed analysis and enqueue it, preserving transcript JSON."""
        current = self.repository.get_analysis(job_id)
        if current is None:
            return self.request_analysis(job_id, **metadata)
        if current["status"] in {
            AnalysisStatus.QUEUED.value,
            AnalysisStatus.PROCESSING.value,
        }:
            return current
        self.repository.update_analysis(
            job_id,
            status=AnalysisStatus.QUEUED,
            updated_at=utc_now(),
            # A retry represents a new attempt.  Do not let a prior completed
            # payload appear alongside the queued lifecycle or be mistaken
            # for the result of this attempt.
            result=None,
            error=None,
            actual_model=None,
            chunk_count=0,
        )
        self.analysis_queue.put(job_id)
        return self.repository.get_analysis(job_id)  # type: ignore[return-value]
