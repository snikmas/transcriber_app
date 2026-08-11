"""Strict, provider-independent schema for meeting insights.

These models are the final trust boundary for model output.  Transcript text is
never interpreted by these validators as instructions; only explicitly shaped,
timestamp-backed fields are accepted.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from .statuses import AnalysisProfile, ProviderProtocol

_DESCRIPTION = Annotated[str, Field(min_length=1)]
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("description", mode="before", check_fields=False)
    @classmethod
    def _description_not_blank(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("description must not be blank")
        return value


class TimestampEvidence(_StrictModel):
    # Strict numeric types keep provider strings and booleans out of the
    # evidence boundary while still accepting ordinary integer timestamps.
    start_seconds: StrictFloat = Field(ge=0)
    end_seconds: StrictFloat = Field(ge=0)

    @field_validator("start_seconds", "end_seconds")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("timestamp must be finite")
        return value

    @model_validator(mode="after")
    def _ordered(self) -> TimestampEvidence:
        if self.start_seconds > self.end_seconds:
            raise ValueError("start_seconds must be less than or equal to end_seconds")
        return self

    def is_within(self, duration_seconds: float) -> bool:
        """Return whether this evidence range is contained in a transcript."""

        if not math.isfinite(duration_seconds) or duration_seconds < 0:
            raise ValueError("duration_seconds must be finite and non-negative")
        return self.end_seconds <= duration_seconds

    def validate_duration(self, duration_seconds: float) -> TimestampEvidence:
        if not self.is_within(duration_seconds):
            raise ValueError("timestamp evidence exceeds transcript duration")
        return self

    def validate_against_duration(self, duration_seconds: float) -> TimestampEvidence:
        """Compatibility alias for callers that name the transcript boundary explicitly."""

        return self.validate_duration(duration_seconds)


def _normalise_nullable(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _validate_deadline(value: object) -> object:
    value = _normalise_nullable(value)
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ValueError("deadline must be an unambiguous ISO date (YYYY-MM-DD) or null")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("deadline must be a valid ISO date (YYYY-MM-DD)") from exc
    return value


class DecisionItem(_StrictModel):
    description: _DESCRIPTION
    source_timestamps: list[TimestampEvidence] = Field(min_length=1)


class ActionItem(_StrictModel):
    description: _DESCRIPTION
    owner: str | None = None
    deadline: str | None = None
    status: Literal["open"] = "open"
    source_timestamps: list[TimestampEvidence] = Field(min_length=1)

    _normalise_owner = field_validator("owner", mode="before")(_normalise_nullable)
    _normalise_action_deadline = field_validator("deadline", mode="before")(_validate_deadline)


class QuestionItem(_StrictModel):
    description: _DESCRIPTION
    source_timestamps: list[TimestampEvidence] = Field(min_length=1)


class FollowUpItem(_StrictModel):
    description: _DESCRIPTION
    owner: str | None = None
    deadline: str | None = None
    source_timestamps: list[TimestampEvidence] = Field(min_length=1)

    _normalise_owner = field_validator("owner", mode="before")(_normalise_nullable)
    _normalise_followup_deadline = field_validator("deadline", mode="before")(_validate_deadline)


class AnalysisMetadata(_StrictModel):
    profile: AnalysisProfile = AnalysisProfile.MEETING
    provider_id: str = Field(min_length=1)
    protocol: ProviderProtocol
    requested_model: str = Field(min_length=1)
    actual_model: str | None = None
    output_language: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1, default="1")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        validation_alias=AliasChoices("generated_at", "generation_time"),
    )
    chunk_count: StrictInt = Field(ge=0)

    _normalise_actual_model = field_validator("actual_model", mode="before")(_normalise_nullable)

    @property
    def generation_time(self) -> datetime:
        return self.generated_at


class MeetingAnalysis(_StrictModel):
    generated_title: str | None = Field(
        default=None,
        validation_alias=AliasChoices("generated_title", "title"),
    )
    summary: _DESCRIPTION
    decisions: list[DecisionItem] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[QuestionItem] = Field(default_factory=list)
    follow_ups: list[FollowUpItem] = Field(default_factory=list)
    metadata: AnalysisMetadata

    _normalise_title = field_validator("generated_title", mode="before")(_normalise_nullable)

    @property
    def title(self) -> str | None:
        """Compatibility accessor for clients that call the generated title simply title."""

        return self.generated_title

    def validate_timestamps(self, duration_seconds: float) -> MeetingAnalysis:
        """Validate every evidence range against the authoritative transcript duration."""

        for item in (*self.decisions, *self.action_items, *self.open_questions, *self.follow_ups):
            for evidence in item.source_timestamps:
                evidence.validate_duration(duration_seconds)
        return self
