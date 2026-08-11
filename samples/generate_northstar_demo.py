"""Generate the repository-owned, copyright-free Demo audio fixture.

The fixture deliberately contains deterministic low-volume tones rather than a
recording of a real speaker. Demo transcription and meeting analysis are fixed
and do not depend on the waveform; the tones simply make a realistic 72-second
media upload available for UI and ffprobe checks.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

SAMPLE_RATE = 16_000
DURATION_SECONDS = 72
OUTPUT = Path(__file__).with_name("northstar-demo-60s.wav")


def main() -> None:
    total_frames = SAMPLE_RATE * DURATION_SECONDS
    with wave.open(str(OUTPUT), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for index in range(total_frames):
            second = index / SAMPLE_RATE
            # A repeatable three-tone pattern with short quiet gaps; no speech,
            # personal recording, or third-party copyrighted material is used.
            phase = int(second // 3) % 3
            frequency = (220.0, 277.18, 329.63)[phase]
            amplitude = 900 if second % 3 < 2.5 else 0
            sample = int(amplitude * math.sin(2 * math.pi * frequency * second))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        audio.writeframes(frames)


if __name__ == "__main__":
    main()
