from __future__ import annotations

import html
import os
import time
from pathlib import Path

import requests
import streamlit as st

from src.exports import transcript_json, transcript_markdown, transcript_txt

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL_SECONDS", "0.5"))
SAMPLE_PATH = Path(__file__).resolve().parents[1] / "samples" / "northstar-demo.wav"

st.set_page_config(
    page_title="Private Local Transcriber",
    page_icon="🎙️",
    layout="centered",
)

st.markdown(
    """
    <style>
    :root {
      --ink: #eef1f7;
      --muted: #9aa3b5;
      --surface: #171b24;
      --line: #2c3442;
      --accent: #d6f45f;
    }
    .block-container { max-width: 820px; padding-top: 4rem; }
    h1, h2, h3 { letter-spacing: -0.035em; }
    .eyebrow {
      color: var(--accent); font-size: .76rem; font-weight: 700;
      letter-spacing: .12em; text-transform: uppercase; margin-bottom: .5rem;
      display: block; line-height: 1.4; padding-top: .25rem;
    }
    .lede { color: var(--muted); font-size: 1.05rem; line-height: 1.65; }
    .privacy {
      border: 1px solid var(--line); background: var(--surface);
      border-radius: .7rem; padding: .85rem 1rem; margin: 1.25rem 0;
      color: var(--muted);
    }
    .transcript {
      background: #10131a; border: 1px solid var(--line); border-radius: .7rem;
      padding: 1rem 1.2rem; max-height: 380px; overflow-y: auto;
    }
    .segment { display: grid; grid-template-columns: 9rem 1fr; gap: 1rem;
      padding: .55rem 0; border-bottom: 1px solid #222936; }
    .segment:last-child { border: 0; }
    .timestamp { color: var(--accent); font-family: monospace; font-size: .8rem; }
    .copy { color: var(--ink); line-height: 1.55; }
    @media (max-width: 560px) {
      .segment { grid-template-columns: 1fr; gap: .25rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=5)
def get_health() -> dict | None:
    try:
        response = requests.get(f"{API_URL}/health", timeout=3)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def submit_file(filename: str, content: bytes, media_type: str) -> str:
    response = requests.post(
        f"{API_URL}/transcribe",
        files={"file": (filename, content, media_type)},
        timeout=30,
    )
    if response.status_code >= 400:
        detail = response.json().get("detail", {})
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        raise RuntimeError(message or "The API rejected this upload.")
    return response.json()["job_id"]


def wait_for_result(job_id: str, timeout_seconds: int = 300) -> dict:
    deadline = time.monotonic() + timeout_seconds
    status_box = st.empty()
    while time.monotonic() < deadline:
        response = requests.get(f"{API_URL}/transcribe/{job_id}", timeout=10)
        response.raise_for_status()
        job = response.json()
        current_status = job["status"]
        status_box.info(f"Job status: {current_status}")
        if current_status == "completed":
            status_box.empty()
            return job["result"]
        if current_status == "failed":
            raise RuntimeError(job.get("error") or "Transcription failed.")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError("Transcription is still running. Check the job through the API.")


def render_result(result: dict) -> None:
    st.success("Transcript ready")
    columns = st.columns(4, gap="large")
    columns[0].metric("Duration", result["duration_text"])
    columns[1].metric("Segments", len(result["segments"]))
    columns[2].metric("Words", result["word_count"])
    columns[3].metric("Language", result["language"])

    st.subheader("Timestamped transcript")
    rendered_segments = []
    for segment in result["segments"]:
        rendered_segments.append(
            '<div class="segment">'
            f'<span class="timestamp">{html.escape(segment["start_text"])} → '
            f"{html.escape(segment['end_text'])}</span>"
            f'<span class="copy">{html.escape(segment["text"])}</span>'
            "</div>"
        )
    st.markdown(
        f'<div class="transcript">{"".join(rendered_segments)}</div>',
        unsafe_allow_html=True,
    )

    st.subheader("Download")
    txt_col, json_col, md_col = st.columns(3)
    stem = Path(result["filename"]).stem or "transcript"
    txt_col.download_button(
        "TXT",
        transcript_txt(result),
        file_name=f"{stem}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    json_col.download_button(
        "JSON",
        transcript_json(result),
        file_name=f"{stem}.json",
        mime="application/json",
        use_container_width=True,
    )
    md_col.download_button(
        "Markdown",
        transcript_markdown(result),
        file_name=f"{stem}.md",
        mime="text/markdown",
        use_container_width=True,
    )
    st.caption(f"Engine: {result['engine']}")


st.markdown('<div class="eyebrow">Audio and video → timestamped text</div>', unsafe_allow_html=True)
st.title("Private Local Transcriber")
st.markdown(
    '<p class="lede">Upload a meeting, interview, lecture, or short video. '
    "The app creates a durable background job and returns a transcript you can "
    "review or export.</p>",
    unsafe_allow_html=True,
)

health = get_health()
if health:
    mode_label = "Deterministic demo" if health["mode"] == "demo" else "Local Whisper"
    st.markdown(
        '<div class="privacy">🔒 Files are processed by your own API and removed '
        f"after the job finishes. <strong>Mode:</strong> {mode_label} · "
        f"<strong>Upload limit:</strong> {health['max_upload_mb']} MB.</div>",
        unsafe_allow_html=True,
    )
    if health["mode"] == "demo":
        st.info(
            "Demo mode returns a fixed fictional transcript so the complete job and "
            "export workflow can be reviewed without downloading an ML model. Set "
            "`TRANSCRIBER_MODE=local` for real speech recognition."
        )
else:
    st.error(
        f"API unavailable at `{API_URL}`. Start it with `uvicorn main:app`, "
        "or set `API_URL` for Docker."
    )

st.subheader("1. Choose a file")
uploaded = st.file_uploader(
    "Audio or video",
    type=["aac", "avi", "flac", "m4a", "mkv", "mov", "mp3", "mp4", "ogg", "opus", "wav", "webm"],
    help="Supported audio and video formats. Large files take longer on CPU.",
)
use_sample = st.checkbox(
    "Use the bundled demo audio fixture",
    value=False,
    disabled=not SAMPLE_PATH.exists(),
)

if uploaded:
    size_mb = len(uploaded.getvalue()) / (1024 * 1024)
    st.caption(f"Selected: {uploaded.name} · {size_mb:.2f} MB · {uploaded.type}")
elif use_sample:
    st.caption("Selected: northstar-demo.wav · repository-owned generated audio fixture")

st.subheader("2. Transcribe")
if st.button(
    "Start transcription",
    type="primary",
    use_container_width=True,
    disabled=not health or (not uploaded and not use_sample),
):
    st.session_state.pop("result", None)
    try:
        if uploaded:
            filename = uploaded.name
            content = uploaded.getvalue()
            media_type = uploaded.type or "application/octet-stream"
        else:
            filename = SAMPLE_PATH.name
            content = SAMPLE_PATH.read_bytes()
            media_type = "audio/wav"

        with st.spinner("Submitting and processing the job…"):
            job_id = submit_file(filename, content, media_type)
            st.session_state["result"] = wait_for_result(job_id)
    except (requests.RequestException, RuntimeError, TimeoutError) as exc:
        st.error(str(exc))

if st.session_state.get("result"):
    st.divider()
    render_result(st.session_state["result"])
    if st.button("Process another file"):
        st.session_state.pop("result", None)
        st.rerun()

st.divider()
st.caption(
    "Portfolio release: single-process worker queue and SQLite persistence. "
    "Demo mode is deterministic; local mode uses faster-whisper."
)
