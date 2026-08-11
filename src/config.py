from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# These limits are part of the analysis input/retry contract.  Keeping them in
# one place prevents an environment variable from silently expanding the
# amount of work or data a provider request can consume.
MAX_ANALYSIS_ATTEMPTS = 3
MAX_ANALYSIS_CHUNKS = 10
MAX_ANALYSIS_TEXT_CHARS = 120_000
MAX_ANALYSIS_TIMEOUT_SECONDS = 300.0


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
    analysis_mode: str = "demo"
    analysis_provider: str = "demo"
    analysis_protocol: str = "demo"
    analysis_model: str = "deterministic-meeting-v1"
    analysis_base_url: str | None = None
    analysis_output_language: str = "auto"
    analysis_timeout_seconds: float = 60.0
    analysis_max_attempts: int = 3
    analysis_chunk_chars: int = 12_000
    analysis_max_chunks: int = 10
    analysis_max_transcript_chars: int = 120_000
    custom_provider_policy: str = "local-only"
    allow_local_provider_urls: bool = False
    openai_api_key: str | None = field(default=None, repr=False)
    anthropic_api_key: str | None = field(default=None, repr=False)
    openrouter_api_key: str | None = field(default=None, repr=False)
    packyapi_api_key: str | None = field(default=None, repr=False)
    analysis_api_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _validate_analysis_limits(
            timeout_seconds=self.analysis_timeout_seconds,
            max_attempts=self.analysis_max_attempts,
            chunk_chars=self.analysis_chunk_chars,
            max_chunks=self.analysis_max_chunks,
            max_transcript_chars=self.analysis_max_transcript_chars,
        )

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
        analysis_mode=os.getenv("ANALYSIS_MODE", "demo").strip().lower(),
        analysis_provider=os.getenv("ANALYSIS_PROVIDER", "demo").strip().lower(),
        analysis_protocol=os.getenv("ANALYSIS_PROTOCOL", "demo").strip().lower(),
        analysis_model=os.getenv("ANALYSIS_MODEL", "deterministic-meeting-v1").strip(),
        analysis_base_url=os.getenv("ANALYSIS_BASE_URL", "").strip() or None,
        analysis_output_language=os.getenv("ANALYSIS_OUTPUT_LANGUAGE", "auto").strip() or "auto",
        analysis_timeout_seconds=_bounded_float(
            "ANALYSIS_TIMEOUT_SECONDS",
            os.getenv("ANALYSIS_TIMEOUT_SECONDS", "60"),
            minimum=0,
            maximum=MAX_ANALYSIS_TIMEOUT_SECONDS,
        ),
        analysis_max_attempts=_bounded_int(
            "ANALYSIS_MAX_ATTEMPTS",
            os.getenv("ANALYSIS_MAX_ATTEMPTS", "3"),
            minimum=1,
            maximum=MAX_ANALYSIS_ATTEMPTS,
        ),
        analysis_chunk_chars=_bounded_int(
            "ANALYSIS_CHUNK_CHARS",
            os.getenv("ANALYSIS_CHUNK_CHARS", "12000"),
            minimum=1,
            maximum=MAX_ANALYSIS_TEXT_CHARS,
        ),
        analysis_max_chunks=_bounded_int(
            "ANALYSIS_MAX_CHUNKS",
            os.getenv("ANALYSIS_MAX_CHUNKS", "10"),
            minimum=1,
            maximum=MAX_ANALYSIS_CHUNKS,
        ),
        analysis_max_transcript_chars=_bounded_int(
            "ANALYSIS_MAX_TRANSCRIPT_CHARS",
            os.getenv("ANALYSIS_MAX_TRANSCRIPT_CHARS", "120000"),
            minimum=1,
            maximum=MAX_ANALYSIS_TEXT_CHARS,
        ),
        custom_provider_policy=os.getenv("CUSTOM_PROVIDER_POLICY", "local-only").strip().lower(),
        allow_local_provider_urls=_env_bool("ALLOW_LOCAL_PROVIDER_URLS", False),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        packyapi_api_key=os.getenv("PACKYAPI_API_KEY"),
        analysis_api_key=os.getenv("ANALYSIS_API_KEY"),
    )


def _bounded_int(name: str, value: str, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def _bounded_float(name: str, value: str, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not math.isfinite(parsed) or not minimum < parsed <= maximum:
        raise ValueError(f"{name} must be greater than {minimum} and at most {maximum}.")
    return parsed


def _validate_analysis_limits(
    *,
    timeout_seconds: float,
    max_attempts: int,
    chunk_chars: int,
    max_chunks: int,
    max_transcript_chars: int,
) -> None:
    """Validate analysis limits for both env-loaded and directly-built settings."""

    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValueError("ANALYSIS_TIMEOUT_SECONDS must be a number.")
    timeout_is_valid = (
        math.isfinite(timeout_seconds) and 0 < timeout_seconds <= MAX_ANALYSIS_TIMEOUT_SECONDS
    )
    if not timeout_is_valid:
        raise ValueError(
            "ANALYSIS_TIMEOUT_SECONDS must be greater than 0 and at most "
            f"{MAX_ANALYSIS_TIMEOUT_SECONDS}."
        )

    values = {
        "ANALYSIS_MAX_ATTEMPTS": (max_attempts, 1, MAX_ANALYSIS_ATTEMPTS),
        "ANALYSIS_CHUNK_CHARS": (chunk_chars, 1, MAX_ANALYSIS_TEXT_CHARS),
        "ANALYSIS_MAX_CHUNKS": (max_chunks, 1, MAX_ANALYSIS_CHUNKS),
        "ANALYSIS_MAX_TRANSCRIPT_CHARS": (max_transcript_chars, 1, MAX_ANALYSIS_TEXT_CHARS),
    }
    for name, (value, minimum, maximum) in values.items():
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}.")

    if chunk_chars > max_transcript_chars:
        raise ValueError("ANALYSIS_CHUNK_CHARS cannot exceed ANALYSIS_MAX_TRANSCRIPT_CHARS.")
    if max_transcript_chars > chunk_chars * max_chunks:
        raise ValueError(
            "ANALYSIS_MAX_TRANSCRIPT_CHARS cannot exceed "
            "ANALYSIS_CHUNK_CHARS multiplied by ANALYSIS_MAX_CHUNKS."
        )


def provider_key(settings: Settings, provider: str | None = None) -> str | None:
    """Resolve a provider key without exposing it in settings representations."""

    selected = (provider or settings.analysis_provider).strip().lower()
    keys: Mapping[str, str | None] = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "openrouter": settings.openrouter_api_key,
        "packyapi": settings.packyapi_api_key,
    }
    return keys.get(selected) or settings.analysis_api_key


def validate_live_analysis(settings: Settings, *, provider: str | None = None) -> None:
    """Validate live-only requirements at request time, not demo application startup."""

    mode = settings.analysis_mode.strip().lower()
    if mode == "demo":
        return
    if mode != "live":
        raise ValueError("ANALYSIS_MODE must be 'demo' or 'live'.")
    if not provider_key(settings, provider):
        raise ValueError("provider_key_missing")
    if settings.analysis_chunk_chars > settings.analysis_max_transcript_chars:
        raise ValueError("ANALYSIS_CHUNK_CHARS cannot exceed ANALYSIS_MAX_TRANSCRIPT_CHARS.")


def public_analysis_config(settings: Settings) -> dict[str, object]:
    """Return health-shaped configuration with credentials intentionally omitted."""

    return {
        "mode": settings.analysis_mode,
        "provider": settings.analysis_provider,
        "protocol": settings.analysis_protocol,
        "model": settings.analysis_model,
        "output_language": settings.analysis_output_language,
        "timeout_seconds": settings.analysis_timeout_seconds,
        "max_attempts": settings.analysis_max_attempts,
        "chunk_chars": settings.analysis_chunk_chars,
        "max_chunks": settings.analysis_max_chunks,
        "max_transcript_chars": settings.analysis_max_transcript_chars,
        "has_provider_key": bool(provider_key(settings)),
    }
