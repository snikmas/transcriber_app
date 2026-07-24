from __future__ import annotations

import json


def transcript_txt(result: dict) -> str:
    return "\n".join(
        f"[{segment['start_text']} → {segment['end_text']}] {segment['text']}"
        for segment in result["segments"]
    )


def transcript_markdown(result: dict) -> str:
    lines = [
        f"# Transcript: {result['filename']}",
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
