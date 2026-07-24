from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from src.config import Settings
from src.constants import VIDEO_SUFFIXES
from src.parsers import build_result


@dataclass(frozen=True)
class DemoSegment:
    start: float
    end: float
    text: str


DEMO_SEGMENTS = [
    DemoSegment(0.0, 4.2, "Welcome to the Northstar Studio project update."),
    DemoSegment(
        4.2,
        10.4,
        "This fictional recording demonstrates private local transcription.",
    ),
    DemoSegment(
        10.4,
        17.8,
        "The release includes durable jobs, timestamped segments, and three export formats.",
    ),
    DemoSegment(
        17.8,
        24.0,
        "In local mode, the same workflow runs with faster Whisper on your machine.",
    ),
]


class TranscriptionEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def model(self):
        if self.settings.mode == "demo":
            return None
        if self.settings.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install runtime dependencies first."
            ) from exc
        return WhisperModel(
            self.settings.model_name,
            device=self.settings.device,
            compute_type=self.settings.compute_type,
        )

    @property
    def readiness(self) -> str:
        return "demo-ready" if self.settings.mode == "demo" else "loads-on-first-job"

    def transcribe(self, input_path: Path, filename: str) -> dict:
        if self.settings.mode == "demo":
            return build_result(
                filename=filename,
                segments=DEMO_SEGMENTS,
                duration_seconds=24,
                language="en",
                language_probability=1,
                engine="deterministic-demo",
            )

        media_path = self._prepare_media(input_path)
        segments, info = self.model.transcribe(str(media_path), vad_filter=True)
        return build_result(
            filename=filename,
            segments=list(segments),
            duration_seconds=info.duration,
            language=info.language,
            language_probability=info.language_probability,
            engine=f"faster-whisper/{self.settings.model_name}",
        )

    @staticmethod
    def _prepare_media(input_path: Path) -> Path:
        if input_path.suffix.lower() not in VIDEO_SUFFIXES:
            return input_path
        output_path = input_path.with_name("audio.wav")
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                timeout=300,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg is required for video uploads but was not found.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"ffmpeg could not read this video: {message[-300:]}") from exc
        return output_path
