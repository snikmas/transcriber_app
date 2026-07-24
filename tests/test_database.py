from pathlib import Path

from src.constants import JobStatus
from src.database.database import JobRepository


def job_payload(job_id: str, status: str = "queued") -> dict:
    return {
        "job_id": job_id,
        "filename": "sample.wav",
        "media_type": "audio/wav",
        "input_path": "/tmp/sample.wav",
        "status": status,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def test_repository_persists_result_across_instances(tmp_path: Path):
    path = tmp_path / "jobs.sqlite3"
    first = JobRepository(path)
    first.initialize()
    first.create(job_payload("job-1"))
    first.update(
        "job-1",
        status=JobStatus.COMPLETED,
        updated_at="2026-01-01T00:01:00+00:00",
        result={"text": "done"},
    )

    second = JobRepository(path)

    assert second.get("job-1")["result"] == {"text": "done"}


def test_repository_marks_interrupted_jobs_failed(tmp_path: Path):
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    repository.create(job_payload("queued"))
    repository.create(job_payload("processing", status="processing"))

    recovered = repository.recover_incomplete("2026-01-02T00:00:00+00:00")

    assert recovered == 2
    assert repository.get("queued")["status"] == "failed"
    assert "restart" in repository.get("processing")["error"]


def test_repository_delete_reports_presence(tmp_path: Path):
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    repository.create(job_payload("job-1"))

    assert repository.delete("job-1") is True
    assert repository.delete("job-1") is False
