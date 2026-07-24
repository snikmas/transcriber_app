import json

from src.exports import transcript_json, transcript_markdown, transcript_txt

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
