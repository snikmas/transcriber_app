"""Provider-neutral bounded analysis orchestration."""

from __future__ import annotations

import json
import math
import time
from typing import Any

from .chunking import TranscriptChunk, chunk_transcript
from .parsing import AnalysisParseError, parse_meeting_analysis
from .prompts import MEETING_JSON_CONTRACT, build_meeting_prompt
from .providers import AnalysisProvider, ProviderError, ProviderResponse, is_retryable_error


class MeetingAnalysisService:
    """Extract each transcript chunk independently, then synthesize once."""

    def __init__(
        self,
        provider: AnalysisProvider,
        *,
        model: str,
        output_language: str = "auto",
        max_attempts: int = 3,
        chunk_chars: int = 12_000,
        max_chunks: int = 10,
        max_transcript_chars: int = 120_000,
        timeout_seconds: float = 60.0,
        sleep=time.sleep,
    ):
        self.provider = provider
        self.model = model
        self.output_language = output_language
        self.max_attempts = max(1, min(max_attempts, 3))
        self.chunk_chars = chunk_chars
        self.max_chunks = max_chunks
        self.max_transcript_chars = max_transcript_chars
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
            raise ValueError("timeout_seconds must be a finite positive number")
        if not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        self.timeout_seconds = timeout_seconds
        self._sleep = sleep

    def analyze(
        self,
        segments: list[object] | tuple[object, ...],
        *,
        duration_seconds: float | None = None,
    ) -> Any:
        chunks = chunk_transcript(
            segments,
            max_chars=self.chunk_chars,
            max_chunks=self.max_chunks,
            max_transcript_chars=self.max_transcript_chars,
        )
        transcript = _format_chunks(chunks)
        # Every extraction request contains one bounded chunk.  Responses stay
        # opaque until the final schema boundary, where synthesis combines them.
        chunk_responses = [
            self._generate(
                [
                    {
                        "role": "user",
                        "content": build_meeting_prompt(
                            _format_chunk(chunk), output_language=self.output_language
                        ),
                    }
                ]
            )
            for chunk in chunks
        ]
        synthesis_material = _bounded_synthesis_material(
            chunk_responses, max_chars=self.max_transcript_chars
        )
        synthesis_prompt = (
            "Synthesize the independently extracted meeting chunks below into one "
            "schema-valid MeetingAnalysis JSON object. Preserve only evidence and "
            "timestamps present in the chunk results; do not invent details. "
            f"Write text in {self.output_language}.\n\n{MEETING_JSON_CONTRACT}\n\n"
            "<chunk_analyses>\n"
            f"{synthesis_material}\n</chunk_analyses>"
        )
        response = self._generate([{"role": "user", "content": synthesis_prompt}])
        metadata = {
            "provider_id": self.provider.provider_id,
            "protocol": self.provider.protocol,
            "requested_model": self.model,
            "output_language": self.output_language,
            "prompt_version": "meeting_v1",
            "schema_version": "1",
            "chunk_count": len(chunks),
        }
        # ``response`` is the bounded synthesis result, not a transcript-sized
        # request assembled from all source segments.
        try:
            return parse_meeting_analysis(
                response.structured if response.structured is not None else response.text,
                metadata={**metadata, "actual_model": response.actual_model},
                duration_seconds=duration_seconds,
            )
        except AnalysisParseError as first_error:
            repair_messages = [
                {
                    "role": "user",
                    "content": (
                        "Return exactly one schema-valid MeetingAnalysis JSON object. "
                        "Use only the original transcript evidence below and do not "
                        "repeat or quote any previous output.\n\n"
                        "<original_transcript>\n"
                        f"{transcript}\n"
                        "</original_transcript>"
                    ),
                }
            ]
            try:
                repaired = self._generate(repair_messages, attempts=1)
                return parse_meeting_analysis(
                    repaired.structured if repaired.structured is not None else repaired.text,
                    metadata={**metadata, "actual_model": repaired.actual_model},
                    duration_seconds=duration_seconds,
                )
            except (AnalysisParseError, ProviderError) as exc:
                if isinstance(exc, ProviderError):
                    raise
                raise AnalysisParseError(
                    "provider output failed schema validation"
                ) from first_error

    def _generate(
        self, messages: list[dict[str, str]], *, attempts: int | None = None
    ) -> ProviderResponse:
        total = attempts or self.max_attempts
        last: ProviderError | None = None
        for index in range(total):
            try:
                return self.provider.generate(
                    messages, model=self.model, timeout=self.timeout_seconds
                )
            except ProviderError as exc:
                last = exc
                if not is_retryable_error(exc) or index == total - 1:
                    raise
                self._sleep(min(0.25 * (index + 1), 0.5))
        assert last is not None
        raise last


def analyze_transcript(provider: AnalysisProvider, segments: list[object], **kwargs: Any) -> Any:
    """Convenience wrapper used by worker integrations."""

    return MeetingAnalysisService(provider, **kwargs).analyze(segments)


def _format_chunk(chunk: TranscriptChunk) -> str:
    return "\n".join(f"[{item.start:.3f}-{item.end:.3f}] {item.text}" for item in chunk.segments)


def _format_chunks(chunks: list[TranscriptChunk]) -> str:
    return "\n".join(_format_chunk(chunk) for chunk in chunks)


def _bounded_synthesis_material(responses: list[ProviderResponse], *, max_chars: int) -> str:
    material: list[str] = []
    for index, response in enumerate(responses, start=1):
        value: object = response.structured if response.structured is not None else response.text
        if isinstance(value, str):
            encoded = value
        else:
            try:
                encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                encoded = ""
        material.append(f"chunk_{index}: {encoded}")
    result = "\n".join(material)
    if len(result) > max_chars:
        raise AnalysisParseError("analysis synthesis exceeds configured limit")
    return result
