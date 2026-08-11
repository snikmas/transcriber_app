from pathlib import Path
from queue import Queue

from src.analysis.statuses import TranscriptionStatus
from src.database.database import JobRepository
from src.jobs import JobService


def test_job_service_persists_and_queues_job(tmp_path: Path):
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    job_queue: Queue[str] = Queue()
    service = JobService(repository, job_queue)

    job = service.create(
        filename="meeting.wav",
        media_type="audio/wav",
        input_path=tmp_path / "meeting.wav",
    )

    assert repository.get(job["job_id"])["status"] == "queued"
    assert job_queue.get_nowait() == job["job_id"]


def test_request_analysis_enqueues_only_new_active_analysis(tmp_path: Path):
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    repository.create(
        {
            "job_id": "job",
            "filename": "meeting.wav",
            "media_type": "audio/wav",
            "input_path": "/tmp/meeting.wav",
            "status": "queued",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
        }
    )
    repository.update_transcription(
        "job", status=TranscriptionStatus.COMPLETED, updated_at="2026-01-02", result={"text": "ok"}
    )
    job_queue: Queue[str] = Queue()
    analysis_queue: Queue[str] = Queue()
    service = JobService(repository, job_queue, analysis_queue)

    first = service.request_analysis("job")
    second = service.request_analysis("job")

    assert first == second
    assert analysis_queue.qsize() == 1
    assert analysis_queue.get_nowait() == "job"
