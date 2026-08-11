from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

_PRIVATE_ANALYSIS_FIELDS = frozenset(
    {"api_key", "prompt", "raw_provider_payload", "lease_id", "input_path"}
)


def _without_private_fields(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: _without_private_fields(item)
            for key, item in value.items()
            if key not in _PRIVATE_ANALYSIS_FIELDS
        }
    if isinstance(value, list):
        return [_without_private_fields(item) for item in value]
    return value


def _model_dump(value: object) -> object:
    """Convert a Pydantic model without making exports depend on Pydantic."""

    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value


def _is_job_shaped(value: Mapping[str, Any]) -> bool:
    """Return whether *value* is the public job response shape.

    A transcript result always has ``segments``.  Public jobs wrap that result
    under ``result`` and carry lifecycle fields beside it.
    """

    return "segments" not in value and isinstance(value.get("result"), Mapping)


def _safe_heading(value: object, fallback: str) -> str:
    """Make untrusted text safe to place in a Markdown heading.

    Newlines and other control characters are collapsed so callers cannot
    inject a second heading.  Markdown-significant punctuation is escaped and
    angle brackets are rendered as text rather than HTML.
    """

    if not isinstance(value, str):
        value = fallback
    cleaned = " ".join(part for part in value.replace("\r", " ").replace("\n", " ").split())
    cleaned = cleaned or fallback
    cleaned = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for character in ("\\", "`", "*", "_", "[", "]", "#"):
        cleaned = cleaned.replace(character, f"\\{character}")
    return cleaned


def _safe_metadata_value(value: object) -> str:
    """Render a scalar metadata value without allowing Markdown line breaks."""

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _safe_heading(value, "Not identified")
    return "Not identified"


def _combined_parts(
    transcript: Mapping[str, Any], analysis: object | None
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Normalise direct transcript calls and public job-shaped calls.

    The API stores the authoritative transcript under ``job['result']`` and
    analysis lifecycle metadata under ``job['analysis']``.  Download helpers
    also accept the direct ``(result, MeetingAnalysis)`` form used by callers
    that do not persist jobs.
    """

    source: Mapping[str, Any] = transcript
    if _is_job_shaped(source):
        source = source["result"]
        if analysis is None:
            analysis = transcript.get("analysis")
    transcript_value = dict(source)
    analysis_value = _analysis_export_value(analysis)
    return transcript_value, analysis_value


def _analysis_export_value(value: object | None) -> dict[str, Any] | None:
    if value is None:
        return None
    value = _without_private_fields(_model_dump(value))
    if not isinstance(value, Mapping):
        raise TypeError("analysis must be a mapping or MeetingAnalysis model")

    status = value.get("status")
    if status == "failed":
        # Never publish stale/partial provider output alongside a failed
        # lifecycle state.  The transcript remains authoritative, while the
        # failure is the only trustworthy analysis information.
        exported = {"status": "failed"}
        error = value.get("error")
        if isinstance(error, str) and error:
            exported["error"] = error
        return exported

    # Persisted analysis rows wrap the trusted MeetingAnalysis under ``result``
    # and carry lifecycle status/error beside it.  Flattening the successful
    # result keeps the combined export useful to integrations while retaining
    # the status needed to explain a partial success.
    nested = value.get("result")
    if isinstance(nested, Mapping):
        exported = dict(nested)
        # Keep every public lifecycle/processing field alongside the validated
        # result instead of silently dropping provider and schema metadata.
        # ``result`` itself is intentionally flattened for legacy consumers.
        for key, item in value.items():
            if key != "result" and item is not None:
                exported[key] = item
        return exported

    exported = dict(value)
    # A failed lifecycle row has ``result=None``.  Omitting that storage detail
    # keeps the partial-success contract explicit: transcript is present, but
    # no fabricated insight object is implied.
    if exported.get("result") is None:
        exported.pop("result", None)
    return exported


def transcript_txt(result: dict) -> str:
    return "\n".join(
        f"[{segment['start_text']} → {segment['end_text']}] {segment['text']}"
        for segment in result["segments"]
    )


def _srt_timestamp(seconds: object) -> str:
    """Format a segment offset as the ``HH:MM:SS,mmm`` SRT timestamp."""

    try:
        total_ms = max(0, round(float(seconds) * 1000))
    except (TypeError, ValueError):
        total_ms = 0
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcript_srt(result: dict) -> str:
    """Return a standard UTF-8 SubRip subtitle document."""

    blocks: list[str] = []
    for index, segment in enumerate(result.get("segments", []), start=1):
        start = _srt_timestamp(segment.get("start_seconds", segment.get("start")))
        end = _srt_timestamp(segment.get("end_seconds", segment.get("end")))
        text = str(segment.get("text", "")).strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def transcript_markdown(result: dict) -> str:
    lines = [
        f"# Transcript: {_safe_heading(result.get('filename'), 'meeting')}",
        "",
        f"- Duration: {result['duration_text']}",
        f"- Language: {result['language']}",
        f"- Engine: {result['engine']}",
        "",
        "## Timestamped transcript",
        "",
    ]
    lines.extend(
        f"**[{segment['start_text']} → {segment['end_text']}]** {segment['text']}"
        for segment in result["segments"]
    )
    return "\n".join(lines)


def transcript_json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def combined_json(transcript: dict, analysis: object | None = None) -> str:
    """Return one UTF-8 JSON document containing transcript and meeting data.

    ``transcript`` may be either the legacy transcript result or a public job
    response.  When analysis has failed, only its explicit lifecycle status and
    safe error are exported; no empty or invented insight fields are added.
    """

    transcript_value, analysis_value = _combined_parts(transcript, analysis)
    if _is_job_shaped(transcript):
        # Keep the public job metadata/lifecycle in a separate envelope.  The
        # authoritative transcript remains the persisted job result, while
        # ``analysis`` contains the validated insight fields plus all public
        # analysis lifecycle/processing metadata.
        job_metadata = _without_private_fields(
            {
                key: value
                for key, value in transcript.items()
                if key not in {"result", "analysis", "input_path"}
            }
        )
        document_analysis = analysis_value
        raw_analysis = analysis if analysis is not None else transcript.get("analysis")
        raw_analysis = _without_private_fields(_model_dump(raw_analysis))
        # Preserve the persisted validated result explicitly as well as the
        # flattened legacy insight fields.  This gives integrations a stable
        # authoritative object while old consumers can keep reading fields
        # directly from ``analysis``.
        if (
            isinstance(document_analysis, dict)
            and isinstance(raw_analysis, Mapping)
            and raw_analysis.get("status") != "failed"
            and isinstance(raw_analysis.get("result"), Mapping)
        ):
            document_analysis = dict(document_analysis)
            document_analysis["result"] = raw_analysis["result"]
        document: dict[str, Any] = {
            "job": job_metadata,
            "transcript": transcript_value,
            "analysis": document_analysis,
        }
        return json.dumps(document, ensure_ascii=False, indent=2)
    return json.dumps(
        {"transcript": transcript_value, "analysis": analysis_value},
        ensure_ascii=False,
        indent=2,
    )


def _format_evidence(evidence: object) -> str:
    if not isinstance(evidence, Mapping):
        return ""
    start = evidence.get("start_seconds")
    end = evidence.get("end_seconds")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return f" [{start:g}s → {end:g}s]"
    return ""


def _format_owner_deadline(item: Mapping[str, Any]) -> str:
    details: list[str] = []
    owner = item.get("owner")
    deadline = item.get("deadline")
    if owner:
        details.append(f"Owner: {owner}")
    else:
        details.append("Owner: Not identified")
    if deadline:
        details.append(f"Deadline: {deadline}")
    else:
        details.append("Deadline: Not identified")
    status = item.get("status")
    if status:
        details.append(f"Status: {status}")
    return f" ({'; '.join(details)})" if details else ""


def _markdown_items(items: object, *, action: bool = False) -> list[str]:
    if not isinstance(items, list):
        return []
    lines: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        description = item.get("description")
        if not isinstance(description, str) or not description:
            continue
        evidence = item.get("source_timestamps", [])
        evidence_text = "".join(
            _format_evidence(entry) for entry in evidence if isinstance(evidence, list)
        )
        details = _format_owner_deadline(item) if action else ""
        lines.append(f"- {description}{details}{evidence_text}")
    return lines


def meeting_notes_markdown(transcript: dict, analysis: object | None = None) -> str:
    """Render a readable combined Meeting Notes document.

    This deliberately distinguishes a failed analysis from an empty analysis,
    so partial-success downloads never imply that the meeting had no insights.
    """

    transcript_value, analysis_value = _combined_parts(transcript, analysis)
    filename = _safe_heading(transcript_value.get("filename"), "meeting")
    lines = [
        f"# Meeting Notes: {filename}",
        "",
        f"- Duration: {transcript_value.get('duration_text', '')}",
        f"- Language: {transcript_value.get('language', '')}",
        f"- Engine: {transcript_value.get('engine', '')}",
        "",
    ]

    if analysis_value is None:
        lines.extend(["## Analysis", "", "Analysis was not requested.", ""])
    elif analysis_value.get("status") == "failed":
        lines.extend(["## Analysis", "", "Analysis failed; transcript retained."])
        error = analysis_value.get("error")
        if isinstance(error, str) and error:
            lines.append(f"Error: {error}")
        lines.append("")
    else:
        title = analysis_value.get("generated_title") or analysis_value.get("title")
        if isinstance(title, str) and title:
            lines.extend([f"## {_safe_heading(title, 'Meeting Notes')}", ""])
        summary = analysis_value.get("summary")
        if isinstance(summary, str) and summary:
            lines.extend(["## Summary", "", summary, ""])
        for heading, key, is_action in (
            ("Decisions", "decisions", False),
            ("Action Items", "action_items", True),
            ("Open Questions", "open_questions", False),
            ("Follow-ups", "follow_ups", True),
        ):
            lines.extend([f"## {heading}", ""])
            items = _markdown_items(analysis_value.get(key), action=is_action)
            lines.extend(items or ["None recorded."])
            lines.append("")

    lines.extend(["## Timestamped Transcript", ""])
    lines.extend(
        f"**[{segment['start_text']} → {segment['end_text']}]** {segment['text']}"
        for segment in transcript_value.get("segments", [])
    )
    lines.extend(["", "## Processing Metadata", ""])
    lines.extend(_processing_metadata_lines(transcript, analysis_value))
    return "\n".join(lines)


def _processing_metadata_lines(
    source: Mapping[str, Any], analysis: Mapping[str, Any] | None
) -> list[str]:
    """Render an allowlisted, private-field-free processing summary."""

    lines: list[str] = []
    job = (
        {
            key: value
            for key, value in source.items()
            if key not in {"result", "analysis", "input_path"}
        }
        if _is_job_shaped(source)
        else {}
    )
    fields: list[tuple[str, object]] = []
    for key, label in (
        ("status", "Job status"),
        ("transcription_status", "Transcription status"),
        ("analysis_status", "Analysis status"),
        ("created_at", "Created"),
        ("updated_at", "Updated"),
    ):
        if key in job and job[key] is not None:
            fields.append((label, job[key]))

    metadata = analysis.get("metadata") if isinstance(analysis, Mapping) else None
    if not isinstance(metadata, Mapping):
        metadata = {}
    for key, label in (
        ("status", "Analysis lifecycle"),
        ("profile", "Profile"),
        ("provider_id", "Provider"),
        ("protocol", "Protocol"),
        ("requested_model", "Requested model"),
        ("actual_model", "Actual model"),
        ("output_language", "Output language"),
        ("prompt_version", "Prompt version"),
        ("schema_version", "Schema version"),
        ("generated_at", "Generated at"),
        ("chunk_count", "Chunks"),
    ):
        value = analysis.get(key) if isinstance(analysis, Mapping) else None
        if value is None:
            value = metadata.get(key)
        if value is not None:
            fields.append((label, value))

    if not fields:
        return ["- No processing metadata available."]
    for label, value in fields:
        # Values are metadata, not headings, but collapse controls to avoid
        # malformed Markdown and never emit private path/key fields.
        safe_value = _safe_metadata_value(value)
        lines.append(f"- {label}: {safe_value}")
    return lines


# Name used by the UI/product copy; keep the explicit combined_markdown alias
# for integrations that mirror transcript_markdown.
combined_markdown = meeting_notes_markdown
