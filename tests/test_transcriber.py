from pathlib import Path
from unittest.mock import Mock, patch

from src.transcriber import TranscriptionEngine


def test_demo_engine_is_deterministic(settings, tmp_path: Path):
    engine = TranscriptionEngine(settings)

    first = engine.transcribe(tmp_path / "one.wav", "one.wav")
    second = engine.transcribe(tmp_path / "two.wav", "two.wav")

    assert first["text"] == second["text"]
    assert first["filename"] == "one.wav"
    assert first["engine"] == "deterministic-demo"


def test_video_preparation_uses_unique_sibling_audio(tmp_path: Path):
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"video")
    completed = Mock()
    completed.stderr = b""

    with patch("src.transcriber.subprocess.run", return_value=completed) as run:
        output = TranscriptionEngine._prepare_media(input_path)

    assert output == tmp_path / "audio.wav"
    command = run.call_args.args[0]
    assert str(input_path) in command
    assert str(output) in command
