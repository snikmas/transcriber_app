from types import SimpleNamespace

from src.parsers import build_result, format_timestamp


def test_format_timestamp():
    assert format_timestamp(0) == "0:00:00"
    assert format_timestamp(213) == "0:03:33"
    assert format_timestamp(-2) == "0:00:00"


def test_build_result_creates_text_and_metadata():
    segments = [
        SimpleNamespace(start=0, end=2.4, text=" Hello world. "),
        SimpleNamespace(start=2.4, end=5, text="Second segment."),
    ]

    result = build_result(
        filename="sample.wav",
        segments=segments,
        duration_seconds=5,
        language="en",
        language_probability=0.95,
        engine="test",
    )

    assert result["text"] == "Hello world. Second segment."
    assert result["word_count"] == 4
    assert result["segments"][0]["start_text"] == "0:00:00"
    assert result["language"] == "EN"
