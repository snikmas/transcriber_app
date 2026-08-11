import json

from samples.meeting_fixture import MEETING_TRANSCRIPT, meeting_fixture
from src.analysis.schemas import MeetingAnalysis
from src.exports import (
    combined_json,
    meeting_notes_markdown,
    transcript_json,
    transcript_markdown,
    transcript_srt,
    transcript_txt,
)

RESULT = {
    "filename": "meeting.wav",
    "duration_text": "0:00:04",
    "language": "EN",
    "engine": "demo",
    "segments": [
        {
            "start_text": "0:00:00",
            "end_text": "0:00:04",
            "text": "Hello <team>.",
        }
    ],
}


def test_txt_export():
    assert transcript_txt(RESULT) == "[0:00:00 → 0:00:04] Hello <team>."


def test_markdown_export():
    output = transcript_markdown(RESULT)

    assert output.startswith("# Transcript: meeting.wav")
    assert "**[0:00:00 → 0:00:04]** Hello <team>." in output


def test_json_export():
    assert json.loads(transcript_json(RESULT)) == RESULT


def test_srt_export_uses_millisecond_timestamps():
    result = {
        **RESULT,
        "segments": [
            {
                **RESULT["segments"][0],
                "start_seconds": 1.234,
                "end_seconds": 4.5,
            }
        ],
    }

    assert transcript_srt(result) == ("1\n00:00:01,234 --> 00:00:04,500\nHello <team>.\n")


def test_meeting_fixture_is_schema_valid_and_evidence_is_within_transcript():
    transcript, analysis = meeting_fixture()
    validated = MeetingAnalysis.model_validate(analysis)
    validated.validate_timestamps(transcript["duration_seconds"])

    descriptions = {item.description for item in validated.decisions}
    assert any("September 15" in description for description in descriptions)
    assert validated.action_items[0].owner == "Maya"
    assert validated.action_items[0].deadline == "2026-08-20"
    assert any(item.owner is None for item in validated.action_items)
    assert validated.open_questions


def test_combined_json_round_trips_multilingual_content():
    transcript = {
        **RESULT,
        "filename": "会议-совещание.wav",
        "text": "Привет, команда. 你好" + "\uff0c" + "团队。",
    }
    analysis = {
        "generated_title": "Проект / 项目",
        "summary": "Обсудили следующий шаг。下一步已讨论。",
        "decisions": [],
        "action_items": [],
        "open_questions": [],
        "follow_ups": [],
        "metadata": {
            "provider_id": "demo",
            "protocol": "demo",
            "requested_model": "fixture",
            "output_language": "mixed",
            "prompt_version": "fixture",
            "chunk_count": 1,
        },
    }

    exported = json.loads(combined_json(transcript, analysis))

    assert exported["transcript"] == transcript
    assert exported["analysis"] == analysis
    assert "Привет" in combined_json(transcript, analysis)
    assert "你好" in combined_json(transcript, analysis)


def test_meeting_notes_markdown_contains_sections_and_multilingual_text():
    transcript = {**RESULT, "filename": "会议-совещание.wav"}
    analysis = {
        "summary": "Обсудили 你好",
        "decisions": [],
        "action_items": [
            {
                "description": "Confirm the rota",
                "owner": None,
                "deadline": None,
                "status": "open",
                "source_timestamps": [{"start_seconds": 0.0, "end_seconds": 4.0}],
            }
        ],
        "open_questions": [],
        "follow_ups": [],
        "metadata": {"provider_id": "demo"},
    }

    output = meeting_notes_markdown(transcript, analysis)

    assert "# Meeting Notes: 会议-совещание.wav" in output
    assert "## Summary" in output
    assert "## Action Items" in output
    assert "Обсудили 你好" in output
    assert "Owner: Not identified" in output
    assert "[0s → 4s]" in output


def test_partial_success_export_keeps_transcript_without_fabricated_insights():
    failed_job = {
        "result": MEETING_TRANSCRIPT,
        "analysis": {
            "status": "failed",
            "error": "Analysis failed.",
            "result": None,
        },
    }

    exported = json.loads(combined_json(failed_job))
    markdown = meeting_notes_markdown(failed_job)

    assert exported["transcript"] == MEETING_TRANSCRIPT
    assert exported["analysis"] == {"status": "failed", "error": "Analysis failed."}
    assert "Analysis failed; transcript retained." in markdown
    assert "## Decisions" not in markdown
    assert "Northstar team reviewed" in markdown


def test_combined_export_does_not_include_provider_secrets_or_prompts():
    analysis = {
        "status": "completed",
        "result": {"summary": "Safe summary", "api_key": "secret"},
        "api_key": "secret",
        "prompt": "private prompt",
    }

    output = combined_json(RESULT, analysis)

    assert "secret" not in output
    assert "private prompt" not in output
    assert json.loads(output)["analysis"] == {"summary": "Safe summary", "status": "completed"}


def test_job_combined_export_preserves_public_lifecycle_and_validated_result():
    transcript, analysis = meeting_fixture()
    job = {
        "job_id": "job-123",
        "filename": transcript["filename"],
        "media_type": "audio/wav",
        "status": "partial_success",
        "transcription_status": "completed",
        "analysis_status": "completed",
        "created_at": "2026-08-11T00:00:00Z",
        "updated_at": "2026-08-11T00:01:00Z",
        "input_path": "/private/uploads/job-123/input.wav",
        "result": transcript,
        "analysis": {
            "analysis_id": "analysis-123",
            "job_id": "job-123",
            "status": "completed",
            "provider_id": "demo",
            "protocol": "demo",
            "requested_model": "fixture",
            "schema_version": "7",
            "chunk_count": 1,
            "result": analysis,
        },
    }

    exported = json.loads(combined_json(job))

    assert exported["job"]["job_id"] == "job-123"
    assert exported["job"]["analysis_status"] == "completed"
    assert "input_path" not in exported["job"]
    assert exported["transcript"] == transcript
    assert exported["analysis"]["result"] == analysis
    assert exported["analysis"]["schema_version"] == "7"
    assert exported["analysis"]["metadata"]["schema_version"] == "1"


def test_markdown_sanitizes_headings_and_appends_processing_metadata():
    transcript = {**RESULT, "filename": "unsafe\n# forged"}
    analysis = {
        "generated_title": "Title\n## forged *heading*",
        "summary": "Safe",
        "decisions": [],
        "action_items": [{"description": "Do it", "owner": None, "deadline": None}],
        "open_questions": [],
        "follow_ups": [],
        "metadata": {"schema_version": "9", "chunk_count": 2},
    }

    output = meeting_notes_markdown(transcript, analysis)

    assert "# Meeting Notes: unsafe \\# forged" in output
    assert "## Title \\#\\# forged \\*heading\\*" in output
    assert "## Processing Metadata" in output
    assert output.index("## Processing Metadata") > output.index("## Timestamped Transcript")
    assert "Owner: Not identified" in output
    assert "Deadline: Not identified" in output
    assert "- Schema version: 9" in output
    assert "- Chunks: 2" in output
