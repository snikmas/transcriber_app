"""Small, framework-free helpers for Streamlit session state."""

from __future__ import annotations

from typing import Any


class JobStatusView:
    """Update one Streamlit placeholder instead of appending status messages."""

    def __init__(self, status_container: Any) -> None:
        self._slot = status_container.empty()

    def show(self, transcription: str, analysis: str) -> None:
        self._slot.info(f"Transcription: {transcription} · Analysis: {analysis}")


def visible_history_jobs(
    jobs: list[dict], session_job_ids: set[str], *, include_saved: bool
) -> list[dict]:
    """Hide jobs from earlier browser sessions unless the user opts in."""

    if include_saved:
        return jobs
    return [job for job in jobs if job.get("job_id") in session_job_ids]
