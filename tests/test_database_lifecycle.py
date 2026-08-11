import sqlite3
from pathlib import Path

from src.analysis.statuses import AnalysisStatus, TranscriptionStatus
from src.database.database import JobRepository


def _legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, media_type TEXT NOT NULL,
                input_path TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, result_json TEXT, error TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "old",
                "meeting.wav",
                "audio/wav",
                "/tmp/meeting.wav",
                "completed",
                "2026-01-01",
                "2026-01-01",
                '{"text":"keep me"}',
                None,
            ),
        )


def test_v1_migration_is_idempotent_and_keeps_transcript(tmp_path: Path):
    path = tmp_path / "jobs.sqlite3"
    _legacy_database(path)
    repository = JobRepository(path)
    repository.initialize()
    repository.create_analysis("old")
    repository.update_analysis(
        "old", status=AnalysisStatus.FAILED, updated_at="2026-01-02", error="provider failed\ntrace"
    )
    repository.initialize()

    job = repository.get("old")
    assert job["transcription_status"] == TranscriptionStatus.COMPLETED.value
    assert job["status"] == "partial_success"
    assert job["result"] == {"text": "keep me"}
    assert repository.get_analysis("old")["error"] == "provider failed"


def test_analysis_failure_recovery_and_delete_cascade(tmp_path: Path):
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
        "job", status=TranscriptionStatus.COMPLETED, updated_at="2026-01-01", result={"text": "ok"}
    )
    repository.create_analysis("job")

    assert repository.recover_incomplete("2026-01-02") == 1
    assert repository.get("job")["status"] == "partial_success"
    assert repository.get("job")["result"] == {"text": "ok"}
    assert repository.delete("job") is True
    assert repository.get_analysis("job") is None


def test_analysis_error_persistence_uses_safe_allowlist(tmp_path: Path):
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    repository.create(
        {
            "job_id": "job",
            "filename": "meeting.wav",
            "media_type": "audio/wav",
            "input_path": "/tmp/meeting.wav",
            "status": "completed",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
        }
    )
    repository.create_analysis("job")

    repository.update_analysis(
        "job",
        status=AnalysisStatus.FAILED,
        updated_at="2026-01-02",
        error="provider response sk-live-SECRET123",
    )

    assert repository.get_analysis("job")["error"] == "Analysis failed."
    assert "SECRET123" not in repository.get_analysis("job")["error"]
