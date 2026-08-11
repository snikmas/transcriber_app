"""Stable lifecycle and provider protocol values for meeting analysis."""

from enum import StrEnum


class OverallStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class TranscriptionStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisProfile(StrEnum):
    MEETING = "meeting"


class ProviderProtocol(StrEnum):
    DEMO = "demo"
    OPENAI_RESPONSES = "openai_responses"
    OPENAI_CHAT = "openai_chat"
    ANTHROPIC_MESSAGES = "anthropic_messages"


def _value(value: StrEnum | str) -> str:
    return value.value if isinstance(value, StrEnum) else value


def compose_overall_status(
    transcription_status: TranscriptionStatus | str,
    analysis_status: AnalysisStatus | str,
) -> OverallStatus:
    """Compose the backwards-compatible overall status from two lifecycles."""

    transcription = _value(transcription_status)
    analysis = _value(analysis_status)
    try:
        transcription = TranscriptionStatus(transcription)
        analysis = AnalysisStatus(analysis)
    except ValueError as exc:
        raise ValueError("Unknown transcription or analysis status.") from exc

    if transcription is TranscriptionStatus.QUEUED:
        return OverallStatus.QUEUED
    if transcription is TranscriptionStatus.PROCESSING:
        return OverallStatus.PROCESSING
    if transcription is TranscriptionStatus.FAILED:
        return OverallStatus.FAILED
    if analysis in {AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING}:
        return OverallStatus.PROCESSING
    if analysis is AnalysisStatus.FAILED:
        return OverallStatus.PARTIAL_SUCCESS
    return OverallStatus.COMPLETED
