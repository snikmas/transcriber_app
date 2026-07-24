from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mode: str
    database_path: Path
    upload_dir: Path
    model_name: str
    device: str
    compute_type: str
    offline: bool
    max_upload_mb: int
    poll_interval_seconds: float

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def load_settings() -> Settings:
    mode = os.getenv("TRANSCRIBER_MODE", "demo").strip().lower()
    if mode not in {"demo", "local"}:
        raise ValueError("TRANSCRIBER_MODE must be 'demo' or 'local'.")

    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "100"))
    if max_upload_mb < 1:
        raise ValueError("MAX_UPLOAD_MB must be at least 1.")

    return Settings(
        mode=mode,
        database_path=Path(os.getenv("DATABASE_PATH", "data/jobs.sqlite3")),
        upload_dir=Path(os.getenv("UPLOAD_DIR", "data/uploads")),
        model_name=os.getenv("WHISPER_MODEL", "tiny"),
        device=os.getenv("WHISPER_DEVICE", "cpu"),
        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        offline=_env_bool("WHISPER_OFFLINE", False),
        max_upload_mb=max_upload_mb,
        poll_interval_seconds=float(os.getenv("POLL_INTERVAL_SECONDS", "0.5")),
    )
