from pathlib import Path
from queue import Queue

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
