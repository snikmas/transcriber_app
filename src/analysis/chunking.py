"""Bounded transcript chunking that never splits a timestamped segment."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptChunk:
    segments: tuple[TranscriptSegment, ...]
    text: str
    start: float
    end: float


class ChunkingError(ValueError):
    code = "analysis_input_too_long"


def _segment(item: object) -> TranscriptSegment:
    if isinstance(item, TranscriptSegment):
        start, end, text = item.start, item.end, item.text
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
            or not math.isfinite(float(start))
            or not math.isfinite(float(end))
            or start < 0
            or end < start
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ChunkingError("invalid transcript segment")
        return TranscriptSegment(float(start), float(end), text.strip())
    if not isinstance(item, dict):
        raise ChunkingError("invalid transcript segment")
    try:
        start = float(item.get("start", item.get("start_seconds")))
        end = float(item.get("end", item.get("end_seconds")))
        text = str(item["text"]).strip()
    except (KeyError, TypeError, ValueError) as exc:
        raise ChunkingError("invalid transcript segment") from exc
    if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start or not text:
        raise ChunkingError("invalid transcript segment")
    return TranscriptSegment(start, end, text)


def chunk_transcript(
    segments: list[object] | tuple[object, ...],
    *,
    max_chars: int = 12_000,
    max_chunks: int = 10,
    max_transcript_chars: int | None = 120_000,
) -> list[TranscriptChunk]:
    """Group complete segments into bounded chunks and preserve their timestamps."""

    if max_chars < 1 or max_chunks < 1:
        raise ValueError("chunk limits must be positive")
    parsed = [_segment(item) for item in segments]
    total = sum(len(item.text) for item in parsed) + max(0, len(parsed) - 1)
    if max_transcript_chars is not None and total > max_transcript_chars:
        raise ChunkingError("analysis transcript exceeds configured limit")
    chunks: list[TranscriptChunk] = []
    current: list[TranscriptSegment] = []
    current_chars = 0
    for segment in parsed:
        addition = len(segment.text) + (1 if current else 0)
        if len(segment.text) > max_chars:
            raise ChunkingError("a transcript segment exceeds the chunk limit")
        if current and current_chars + addition > max_chars:
            chunks.append(_make_chunk(current))
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += len(segment.text) + (1 if len(current) > 1 else 0)
    if current:
        chunks.append(_make_chunk(current))
    if len(chunks) > max_chunks:
        raise ChunkingError("analysis transcript requires too many chunks")
    return chunks


def _make_chunk(items: list[TranscriptSegment]) -> TranscriptChunk:
    return TranscriptChunk(
        tuple(items), " ".join(item.text for item in items), items[0].start, items[-1].end
    )


def chunk_segments(
    segments: list[object] | tuple[object, ...], **kwargs: Any
) -> list[TranscriptChunk]:
    return chunk_transcript(segments, **kwargs)
