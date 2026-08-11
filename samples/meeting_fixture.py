"""Repository-owned fictional meeting data for offline demos and evaluation.

The transcript and analysis intentionally describe the same four moments.  It
is plain data so tests can load it without downloading audio or contacting a
provider; callers may pass ``MEETING_ANALYSIS`` through ``MeetingAnalysis`` for
strict validation when needed.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

MEETING_TRANSCRIPT: dict[str, Any] = {
    "filename": "northstar-planning-meeting.wav",
    "duration_seconds": 34.0,
    "duration_text": "0:00:34",
    "language": "EN",
    "language_probability": 1.0,
    "engine": "deterministic-meeting-fixture",
    "segments": [
        {
            "start": 0.0,
            "end": 5.0,
            "start_text": "0:00:00",
            "end_text": "0:00:05",
            "text": "The Northstar team reviewed the September product launch plan.",
        },
        {
            "start": 5.0,
            "end": 12.0,
            "start_text": "0:00:05",
            "end_text": "0:00:12",
            "text": "We decided to launch on September 15, 2026.",
        },
        {
            "start": 12.0,
            "end": 20.0,
            "start_text": "0:00:12",
            "end_text": "0:00:20",
            "text": "Maya owns the release checklist and will finish it by August 20, 2026.",
        },
        {
            "start": 20.0,
            "end": 27.0,
            "start_text": "0:00:20",
            "end_text": "0:00:27",
            "text": "Someone should confirm the final support rota before launch.",
        },
        {
            "start": 27.0,
            "end": 34.0,
            "start_text": "0:00:27",
            "end_text": "0:00:34",
            "text": "We still need to answer whether analytics events are ready for the pilot.",
        },
    ],
    "text": (
        "The Northstar team reviewed the September product launch plan. We decided "
        "to launch on September 15, 2026. Maya owns the release checklist and will "
        "finish it by August 20, 2026. Someone should confirm the final support rota "
        "before launch. We still need to answer whether analytics events are ready "
        "for the pilot."
    ),
    "word_count": 52,
}

MEETING_ANALYSIS: dict[str, Any] = {
    "generated_title": "Northstar September launch planning",
    "summary": (
        "The team agreed on a September 15 launch, assigned Maya the release checklist, "
        "and left support rota and pilot analytics readiness to follow up."
    ),
    "decisions": [
        {
            "description": "Launch the Northstar product on September 15, 2026.",
            "source_timestamps": [{"start_seconds": 5.0, "end_seconds": 12.0}],
        }
    ],
    "action_items": [
        {
            "description": "Finish the release checklist.",
            "owner": "Maya",
            "deadline": "2026-08-20",
            "status": "open",
            "source_timestamps": [{"start_seconds": 12.0, "end_seconds": 20.0}],
        },
        {
            "description": "Confirm the final support rota before launch.",
            "owner": None,
            "deadline": None,
            "status": "open",
            "source_timestamps": [{"start_seconds": 20.0, "end_seconds": 27.0}],
        },
    ],
    "open_questions": [
        {
            "description": "Are analytics events ready for the pilot?",
            "source_timestamps": [{"start_seconds": 27.0, "end_seconds": 34.0}],
        }
    ],
    "follow_ups": [],
    "metadata": {
        "profile": "meeting",
        "provider_id": "demo",
        "protocol": "demo",
        "requested_model": "deterministic-meeting-v1",
        "actual_model": "deterministic-meeting-v1",
        "output_language": "en",
        "prompt_version": "meeting_v1",
        "schema_version": "1",
        "generated_at": "2026-08-11T00:00:00Z",
        "chunk_count": 1,
    },
}


def meeting_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return independent transcript and analysis copies for a test case."""

    return deepcopy(MEETING_TRANSCRIPT), deepcopy(MEETING_ANALYSIS)


# Short aliases make the fixture convenient in notebooks and tests while the
# descriptive names remain the public fixture contract.
TRANSCRIPT = MEETING_TRANSCRIPT
ANALYSIS = MEETING_ANALYSIS
EXPECTED_TRANSCRIPT = MEETING_TRANSCRIPT
EXPECTED_ANALYSIS = MEETING_ANALYSIS
