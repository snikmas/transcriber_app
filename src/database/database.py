from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.analysis.statuses import AnalysisStatus, OverallStatus, TranscriptionStatus
from src.constants import JobStatus

_UNSET = object()
_MIGRATION_VERSION = 2
_RESTART_ERROR = "Processing was interrupted by an application restart."
_SAFE_ANALYSIS_ERRORS = frozenset(
    {
        "provider failed",
        "analysis failed",
        "No analysis engine configured",
        _RESTART_ERROR,
    }
)
_ANALYSIS_ERROR_FALLBACK = "Analysis failed."


class JobRepository:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                self._initialize_in_transaction(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _initialize_in_transaction(self, connection: sqlite3.Connection) -> None:
        current_version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.execute(
            """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    input_path TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT
                )
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
        for name, definition in {
            "transcription_status": "TEXT NOT NULL DEFAULT 'queued'",
            "analysis_status": "TEXT NOT NULL DEFAULT 'not_requested'",
            "transcription_error": "TEXT",
        }.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
        if current_version < _MIGRATION_VERSION:
            connection.execute(
                """
                    UPDATE jobs SET
                        transcription_status = CASE status
                            WHEN 'processing' THEN 'processing'
                            WHEN 'completed' THEN 'completed'
                            WHEN 'failed' THEN 'failed'
                            ELSE 'queued'
                        END,
                        analysis_status = COALESCE(analysis_status, 'not_requested')
                    """
            )
        connection.execute(
            """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    requested_model TEXT NOT NULL,
                    actual_model TEXT,
                    output_language TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    schema_version TEXT NOT NULL DEFAULT '1',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT
                )
                """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_analyses_job_id ON analyses(job_id)")
        connection.execute(f"PRAGMA user_version = {_MIGRATION_VERSION}")

    def create(self, job: dict[str, Any]) -> None:
        transcription_status = job.get("transcription_status", job.get("status", "queued"))
        analysis_status = job.get("analysis_status", AnalysisStatus.NOT_REQUESTED.value)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, filename, media_type, input_path, status,
                    created_at, updated_at, result_json, error,
                    transcription_status, analysis_status, transcription_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["job_id"],
                    job["filename"],
                    job["media_type"],
                    job.get("input_path"),
                    _overall_value(job.get("status"), transcription_status, analysis_status),
                    job["created_at"],
                    job["updated_at"],
                    _encode(job.get("result")),
                    _safe_error(job.get("error")),
                    _value(transcription_status),
                    _value(analysis_status),
                    _safe_error(job.get("transcription_error")),
                ),
            )

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | OverallStatus | str,
        updated_at: str,
        result: dict[str, Any] | object | None = _UNSET,
        error: str | object | None = _UNSET,
        transcription_status: TranscriptionStatus | str | None = None,
        analysis_status: AnalysisStatus | str | None = None,
        transcription_error: str | object | None = _UNSET,
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT transcription_status, analysis_status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Job {job_id} not found")
            status_value = _value(status)
            inferred_transcription = (
                status_value
                if transcription_status is None
                and status_value in {item.value for item in TranscriptionStatus}
                else row["transcription_status"]
            )
            trans = _value(transcription_status or inferred_transcription)
            analysis = _value(analysis_status or row["analysis_status"])
            assignments = [
                "status = ?",
                "updated_at = ?",
                "transcription_status = ?",
                "analysis_status = ?",
            ]
            values: list[Any] = [_value(status), updated_at, trans, analysis]
            if result is not _UNSET:
                assignments.append("result_json = ?")
                values.append(_encode(result))
            if error is not _UNSET:
                assignments.append("error = ?")
                values.append(_safe_error(error))
            if transcription_error is not _UNSET:
                assignments.append("transcription_error = ?")
                values.append(_safe_error(transcription_error))
            values.append(job_id)
            cursor = connection.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Job {job_id} not found")

    def update_transcription(
        self,
        job_id: str,
        *,
        status: TranscriptionStatus | str,
        updated_at: str,
        result: dict[str, Any] | object | None = _UNSET,
        error: str | object | None = _UNSET,
    ) -> None:
        current = self.get(job_id)
        if current is None:
            raise KeyError(f"Job {job_id} not found")
        transcription = _value(status)
        self.update(
            job_id,
            status=compose_job_status(transcription, current["analysis_status"]),
            updated_at=updated_at,
            result=result,
            error=error,
            transcription_status=transcription,
            # Keep the stage-specific diagnostic separate from the legacy
            # overall ``error`` field.  A successful retry clears it, while
            # an omitted value leaves it untouched for intermediate states.
            transcription_error=(
                None if transcription == TranscriptionStatus.COMPLETED.value else error
            ),
        )

    def recover_incomplete(self, updated_at: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = 'failed', transcription_status = 'failed',
                    updated_at = ?, error = ?, transcription_error = ?
                WHERE transcription_status IN ('queued', 'processing')
                """,
                (updated_at, _RESTART_ERROR, _RESTART_ERROR),
            )
            recovered = cursor.rowcount
            cursor = connection.execute(
                """
                UPDATE analyses
                SET status = 'failed', updated_at = ?, error = ?
                WHERE status IN ('queued', 'processing')
                """,
                (updated_at, _RESTART_ERROR),
            )
            recovered += cursor.rowcount
            # Reconcile the denormalized job lifecycle for every failed
            # analysis, including a job whose transcription was interrupted
            # at the same time.  Without this pass a queued/processing
            # analysis could remain exposed as ``analysis_status=queued``
            # after its durable analysis row had been marked failed.
            connection.execute(
                """
                UPDATE jobs
                SET analysis_status = 'failed',
                    status = CASE
                        WHEN transcription_status = 'completed' THEN 'partial_success'
                        ELSE transcription_status
                    END,
                    updated_at = ?,
                    error = CASE
                        WHEN transcription_status = 'completed' THEN COALESCE(error, ?)
                        ELSE error
                    END
                WHERE EXISTS (
                    SELECT 1 FROM analyses
                    WHERE analyses.job_id = jobs.id AND analyses.status = 'failed'
                )
                """,
                (updated_at, _RESTART_ERROR),
            )
        return recovered

    def create_analysis(
        self,
        job_id: str,
        *,
        profile: str = "meeting",
        provider_id: str = "demo",
        protocol: str = "demo",
        requested_model: str = "deterministic-meeting-v1",
        actual_model: str | None = None,
        output_language: str = "auto",
        prompt_version: str = "1",
        schema_version: str = "1",
        chunk_count: int = 0,
        status: AnalysisStatus | str = AnalysisStatus.QUEUED,
        created_at: str | None = None,
        updated_at: str | None = None,
        analysis_id: str | None = None,
    ) -> dict[str, Any]:
        """Create the one analysis record for a transcript, idempotently."""
        analysis, _created = self.create_analysis_if_absent(
            job_id,
            profile=profile,
            provider_id=provider_id,
            protocol=protocol,
            requested_model=requested_model,
            actual_model=actual_model,
            output_language=output_language,
            prompt_version=prompt_version,
            schema_version=schema_version,
            chunk_count=chunk_count,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            analysis_id=analysis_id,
        )
        return analysis

    def create_analysis_if_absent(
        self,
        job_id: str,
        *,
        profile: str = "meeting",
        provider_id: str = "demo",
        protocol: str = "demo",
        requested_model: str = "deterministic-meeting-v1",
        actual_model: str | None = None,
        output_language: str = "auto",
        prompt_version: str = "1",
        schema_version: str = "1",
        chunk_count: int = 0,
        status: AnalysisStatus | str = AnalysisStatus.QUEUED,
        created_at: str | None = None,
        updated_at: str | None = None,
        analysis_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically return the analysis row and whether this call inserted it."""
        now = created_at or updated_at
        if now is None:
            from src.jobs import utc_now

            now = utc_now()
        updated = updated_at or now
        with self._connect() as connection:
            job = connection.execute(
                "SELECT transcription_status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if job is None:
                raise KeyError(f"Job {job_id} not found")
            existing = connection.execute(
                "SELECT * FROM analyses WHERE job_id = ?", (job_id,)
            ).fetchone()
            if existing:
                return self._analysis_from_row(existing), False
            identifier = analysis_id or str(uuid4())
            analysis_value = _value(status)
            cursor = connection.execute(
                """
                INSERT INTO analyses (
                    id, job_id, status, profile, provider_id, protocol,
                    requested_model, actual_model, output_language, prompt_version,
                    schema_version, chunk_count, created_at, updated_at, result_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                ON CONFLICT(job_id) DO NOTHING
                """,
                (
                    identifier,
                    job_id,
                    analysis_value,
                    profile,
                    provider_id,
                    protocol,
                    requested_model,
                    actual_model,
                    output_language,
                    prompt_version,
                    schema_version,
                    chunk_count,
                    now,
                    updated,
                ),
            )
            if cursor.rowcount == 0:
                existing = connection.execute(
                    "SELECT * FROM analyses WHERE job_id = ?", (job_id,)
                ).fetchone()
                if existing is None:
                    raise RuntimeError("Analysis insert did not create or find a row")
                return self._analysis_from_row(existing), False
            connection.execute(
                "UPDATE jobs SET analysis_status = ?, status = ?, updated_at = ? WHERE id = ?",
                (
                    analysis_value,
                    compose_job_status(job["transcription_status"], analysis_value),
                    updated,
                    job_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM analyses WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Analysis insert did not return a row")
            return self._analysis_from_row(row), True

    def get_analysis(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analyses WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._analysis_from_row(row) if row else None

    def update_analysis(
        self,
        job_id: str,
        *,
        status: AnalysisStatus | str,
        updated_at: str,
        result: dict[str, Any] | object | None = _UNSET,
        error: str | object | None = _UNSET,
        actual_model: str | object | None = _UNSET,
        chunk_count: int | object = _UNSET,
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analyses WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Analysis for job {job_id} not found")
            assignments = ["status = ?", "updated_at = ?"]
            values: list[Any] = [_value(status), updated_at]
            for name, value, encoder in (
                ("result_json", result, _encode),
                ("error", error, lambda item: item),
                ("actual_model", actual_model, lambda item: item),
                ("chunk_count", chunk_count, lambda item: item),
            ):
                if value is not _UNSET:
                    assignments.append(f"{name} = ?")
                    values.append(
                        _safe_analysis_error(value) if name == "error" else encoder(value)
                    )
            values.append(job_id)
            connection.execute(
                f"UPDATE analyses SET {', '.join(assignments)} WHERE job_id = ?", values
            )
            job = connection.execute(
                "SELECT transcription_status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if job:
                connection.execute(
                    "UPDATE jobs SET analysis_status = ?, status = ?, updated_at = ? WHERE id = ?",
                    (
                        _value(status),
                        compose_job_status(job["transcription_status"], _value(status)),
                        updated_at,
                        job_id,
                    ),
                )

    def delete(self, job_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _from_row(row: sqlite3.Row) -> dict[str, Any]:
        result = json.loads(row["result_json"]) if row["result_json"] else None
        return {
            "job_id": row["id"],
            "filename": row["filename"],
            "media_type": row["media_type"],
            "input_path": row["input_path"],
            "status": row["status"],
            "transcription_status": row["transcription_status"],
            "analysis_status": row["analysis_status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "result": result,
            "error": row["error"],
            "transcription_error": row["transcription_error"],
        }

    @staticmethod
    def _analysis_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "analysis_id": row["id"],
            "job_id": row["job_id"],
            "status": row["status"],
            "profile": row["profile"],
            "provider_id": row["provider_id"],
            "protocol": row["protocol"],
            "requested_model": row["requested_model"],
            "actual_model": row["actual_model"],
            "output_language": row["output_language"],
            "prompt_version": row["prompt_version"],
            "schema_version": row["schema_version"],
            "chunk_count": row["chunk_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
        }


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _encode(value: Any) -> str | None:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _safe_error(value: Any) -> str | None:
    """Persist a short diagnostic, never a traceback or credential-shaped value."""
    if value is None:
        return None
    text = str(value).splitlines()[0][:500]
    return re.sub(
        r"(?i)(api[_ -]?key|authorization|bearer|token|password)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )


def _safe_analysis_error(value: Any) -> str | None:
    """Persist only explicitly safe analysis diagnostics, never provider text."""
    if value is None:
        return None
    text = str(value).splitlines()[0].strip()
    return text if text in _SAFE_ANALYSIS_ERRORS else _ANALYSIS_ERROR_FALLBACK


def compose_job_status(transcription: str, analysis: str) -> str:
    if transcription in {"queued", "processing", "failed"}:
        return transcription
    if analysis in {"queued", "processing"}:
        return "processing"
    if analysis == "failed":
        return "partial_success"
    return "completed"


def _overall_value(status: Any, transcription: Any, analysis: Any) -> str:
    if status is not None and _value(status) in {item.value for item in OverallStatus}:
        return _value(status)
    return compose_job_status(_value(transcription), _value(analysis))
