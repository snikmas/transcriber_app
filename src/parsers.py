from __future__ import annotations

from datetime import timedelta
from typing import Any


def format_timestamp(seconds: float | int | None) -> str:
    value = max(0, round(float(seconds or 0)))
    return str(timedelta(seconds=value))


def build_result(
    *,
    filename: str,
    segments: list[Any],
    duration_seconds: float,
    language: str,
    language_probability: float,
    engine: str,
) -> dict:
    parsed_segments = [
        {
            "start": float(segment.start),
            "end": float(segment.end),
            "start_text": format_timestamp(segment.start),
            "end_text": format_timestamp(segment.end),
            "text": segment.text.strip(),
        }
        for segment in segments
        if segment.text.strip()
    ]
    text = " ".join(segment["text"] for segment in parsed_segments)
    return {
        "filename": filename,
        "duration_seconds": round(float(duration_seconds), 3),
        "duration_text": format_timestamp(duration_seconds),
        "language": language.upper(),
        "language_probability": round(float(language_probability), 4),
        "engine": engine,
        "segments": parsed_segments,
        "text": text,
        "word_count": len(text.split()),
    }
