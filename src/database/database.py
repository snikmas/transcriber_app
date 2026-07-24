from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.constants import JobStatus


class JobRepository:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
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

    def create(self, job: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, filename, media_type, input_path, status,
                    created_at, updated_at, result_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["job_id"],
                    job["filename"],
                    job["media_type"],
                    job.get("input_path"),
                    job["status"],
                    job["created_at"],
                    job["updated_at"],
                    None,
                    None,
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
        status: JobStatus,
        updated_at: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        result_json = json.dumps(result, ensure_ascii=False) if result else None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, result_json = ?, error = ?
                WHERE id = ?
                """,
                (status.value, updated_at, result_json, error, job_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Job {job_id} not found")

    def recover_incomplete(self, updated_at: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, error = ?
                WHERE status IN (?, ?)
                """,
                (
                    JobStatus.FAILED.value,
                    updated_at,
                    "Processing was interrupted by an application restart.",
                    JobStatus.QUEUED.value,
                    JobStatus.PROCESSING.value,
                ),
            )
        return cursor.rowcount

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
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "result": result,
            "error": row["error"],
        }
