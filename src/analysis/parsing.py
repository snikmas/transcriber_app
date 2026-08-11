"""Safe extraction and validation of model-generated meeting JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from .schemas import MeetingAnalysis


class AnalysisParseError(ValueError):
    """Raised when provider output cannot be trusted as a meeting analysis."""

    code = "invalid_response"


def extract_json_object(value: object) -> dict[str, Any]:
    """Extract exactly one JSON object from structured or textual provider output.

    A fenced object and harmless leading/trailing prose are accepted. Arrays,
    multiple adjacent objects, truncated JSON, and non-JSON text are rejected.
    """

    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        raise AnalysisParseError("provider returned empty content")
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise AnalysisParseError("provider returned truncated fenced JSON")
        text = "\n".join(lines[1:-1]).strip()
    decoder = json.JSONDecoder()
    starts = [index for index, char in enumerate(text) if char == "{"]
    if not starts:
        raise AnalysisParseError("provider returned no JSON object")
    objects: list[dict[str, Any]] = []
    for index in starts:
        try:
            parsed, end = decoder.raw_decode(text[index:])
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(parsed, dict):
            remainder = text[index + end :].strip()
            # A second complete object is ambiguous and must not be selected silently.
            if remainder.startswith("{") or remainder.startswith("```"):
                raise AnalysisParseError("provider returned multiple JSON objects")
            objects.append(parsed)
            break
    if not objects:
        raise AnalysisParseError("provider returned malformed or truncated JSON")
    return objects[0]


def parse_meeting_analysis(
    value: object,
    *,
    metadata: Mapping[str, Any] | None = None,
    duration_seconds: float | None = None,
) -> MeetingAnalysis:
    """Parse and validate an analysis, adding trusted adapter metadata if needed."""

    payload = extract_json_object(value)
    if metadata:
        supplied = payload.get("metadata")
        # Model output is untrusted.  It may contribute optional metadata, but
        # adapter-supplied provenance must always win.
        merged: dict[str, Any] = {}
        if isinstance(supplied, Mapping):
            merged.update(supplied)
        merged.update(metadata)
        payload["metadata"] = merged
    try:
        result = MeetingAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise AnalysisParseError("provider output failed schema validation") from exc
    if duration_seconds is not None:
        try:
            result.validate_timestamps(duration_seconds)
        except ValueError as exc:
            raise AnalysisParseError("provider output contained out-of-range timestamps") from exc
    return result


def parse_provider_output(value: object, **kwargs: Any) -> MeetingAnalysis:
    """Compatibility alias for callers using the provider-neutral name."""

    return parse_meeting_analysis(value, **kwargs)
