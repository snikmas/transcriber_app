from pathlib import Path
from queue import Queue

from src.database.database import JobRepository
from src.worker import TranscriptionWorker


class FakeEngine:
    def transcribe(self, input_path: Path, filename: str) -> dict:
        assert input_path.exists()
        return {"filename": filename, "segments": []}


def _create_job(repository: JobRepository, *, job_id: str, input_path: Path) -> None:
    repository.create(
        {
            "job_id": job_id,
            "filename": input_path.name,
            "media_type": "audio/wav",
            "input_path": str(input_path),
            "status": "queued",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
        }
    )


def test_worker_preserves_legacy_input_parent_outside_upload_root(tmp_path: Path):
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    job_id = "legacy-id"
    external_dir = tmp_path / "legacy-parent" / job_id
    external_dir.mkdir(parents=True)
    input_path = external_dir / "input.wav"
    input_path.write_bytes(b"legacy")
    _create_job(repository, job_id=job_id, input_path=input_path)

    worker = TranscriptionWorker(
        repository,
        Queue(),
        FakeEngine(),
        upload_root=tmp_path / "configured-uploads",
    )
    worker.process(job_id)

    assert external_dir.exists()
    assert input_path.exists()
    assert repository.get(job_id)["transcription_status"] == "completed"


def test_worker_cleans_only_canonical_upload_directory(tmp_path: Path):
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    job_id = "canonical-id"
    upload_root = tmp_path / "configured-uploads"
    job_dir = upload_root / job_id
    job_dir.mkdir(parents=True)
    input_path = job_dir / "input.wav"
    input_path.write_bytes(b"owned")
    _create_job(repository, job_id=job_id, input_path=input_path)

    worker = TranscriptionWorker(repository, Queue(), FakeEngine(), upload_root=upload_root)
    worker.process(job_id)

    assert not job_dir.exists()
