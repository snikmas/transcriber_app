from __future__ import annotations

import html
import os
import time
from pathlib import Path

import requests
import streamlit as st

from src.exports import (
    combined_json,
    meeting_notes_markdown,
    transcript_json,
    transcript_markdown,
    transcript_txt,
)
from src.ui_state import JobStatusView, visible_history_jobs

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL_SECONDS", "0.5"))
JOB_TIMEOUT_SECONDS = 300
PROVIDERS = {
    "OpenAI": {
        "id": "openai",
        "models": ["gpt-4o-mini", "gpt-4o"],
        "env_key": "OPENAI_API_KEY",
    },
    "Anthropic": {
        "id": "anthropic",
        "models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
        "env_key": "ANTHROPIC_API_KEY",
    },
    "OpenRouter": {
        "id": "openrouter",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"],
        "env_key": "OPENROUTER_API_KEY",
    },
    "DeepSeek": {
        "id": "deepseek",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "env_key": "DEEPSEEK_API_KEY",
    },
    "Custom": {
        "id": "custom_openai",
        "models": ["custom-model"],
        "env_key": "ANALYSIS_API_KEY",
    },
}
LANGUAGES = ["auto", "English", "中文", "Русский", "日本語", "Español"]

st.set_page_config(
    page_title="Meeting Notes & Action Tracker",
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
    .block-container { max-width: 820px; padding: 2.25rem 1rem 4rem; }
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
      .block-container { padding-left: .75rem; padding-right: .75rem; }
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
        raise RuntimeError(_message(response, "The API rejected this upload."))
    return response.json()["job_id"]


def _message(response: requests.Response, fallback: str) -> str:
    try:
        detail = response.json().get("detail", {})
    except (ValueError, requests.exceptions.JSONDecodeError):
        detail = {}
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"]
    return str(detail) if detail else fallback


def get_job(job_id: str) -> dict:
    response = requests.get(f"{API_URL}/jobs/{job_id}", timeout=10)
    if response.status_code >= 400:
        raise RuntimeError(_message(response, "The job could not be loaded."))
    return response.json()


def request_analysis(job_id: str, payload: dict[str, str]) -> dict:
    response = requests.post(f"{API_URL}/jobs/{job_id}/analysis", json=payload, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(_message(response, "Analysis could not be started."))
    return response.json()


def retry_analysis(job_id: str, payload: dict[str, str]) -> dict:
    response = requests.post(f"{API_URL}/jobs/{job_id}/analysis/retry", json=payload, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(_message(response, "Analysis retry could not be started."))
    return response.json()


def test_connection(payload: dict[str, str]) -> dict:
    response = requests.post(f"{API_URL}/providers/test", json=payload, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(_message(response, "Provider configuration is invalid."))
    return response.json()


def poll_job(job_id: str, status_view: JobStatusView | None = None) -> dict:
    deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        job = get_job(job_id)
        transcription = job.get("transcription_status", job.get("status"))
        analysis = job.get("analysis_status", "not_requested")
        if status_view is not None:
            status_view.show(transcription, analysis)
        if transcription in {"failed", "completed"} and analysis not in {"queued", "processing"}:
            return job
        time.sleep(POLL_INTERVAL)
    raise TimeoutError("The job is still running. Refresh History to check it later.")


def _analysis_payload(
    provider_label: str, model: str, language: str, base_url: str, protocol: str
) -> dict[str, str]:
    config = PROVIDERS[provider_label]
    payload = {"provider": config["id"], "model": model.strip(), "output_language": language}
    if base_url:
        payload["base_url"] = base_url.strip()
    if provider_label == "Custom":
        payload["provider"] = (
            "custom_anthropic" if protocol == "Anthropic Messages" else "custom_openai"
        )
    return payload


def _render_analysis(analysis: dict | None) -> None:
    if not analysis:
        return
    status = analysis.get("status", "unknown")
    if status == "failed":
        st.warning(f"Analysis failed; transcript retained. {analysis.get('error', '')}".strip())
        return
    if status != "completed":
        st.info(f"Analysis status: {status}")
        return
    result = analysis.get("result") if isinstance(analysis.get("result"), dict) else analysis
    title = result.get("generated_title") or result.get("title")
    if title:
        st.subheader(str(title))
    if result.get("summary"):
        st.markdown(str(result["summary"]))
    for heading, key in (
        ("Decisions", "decisions"),
        ("Action items", "action_items"),
        ("Open questions", "open_questions"),
        ("Follow-ups", "follow_ups"),
    ):
        items = result.get(key) or []
        if items:
            st.markdown(f"**{heading}**")
            for item in items:
                if isinstance(item, dict):
                    details = []
                    if item.get("owner"):
                        details.append(f"Owner: {item['owner']}")
                    if item.get("deadline"):
                        details.append(f"Due: {item['deadline']}")
                    suffix = f" ({'; '.join(details)})" if details else ""
                    st.markdown(f"- {item.get('description', '')}{suffix}")


def render_result(job: dict) -> None:
    result = job.get("result")
    if not isinstance(result, dict):
        st.error(
            job.get("error") or job.get("transcription_error") or "No transcript was produced."
        )
        return
    if job.get("status") == "partial_success":
        st.warning("Transcript ready; meeting analysis failed. You can retry analysis below.")
    else:
        st.success("Transcript ready")
    columns = st.columns(4, gap="large")
    columns[0].metric("Duration", result.get("duration_text", "—"))
    columns[1].metric("Segments", len(result.get("segments", [])))
    columns[2].metric("Words", result.get("word_count", "—"))
    columns[3].metric("Language", result.get("language", "—"))
    st.subheader("Meeting notes")
    _render_analysis(job.get("analysis"))
    st.subheader("Timestamped transcript")
    rendered_segments = []
    for segment in result.get("segments", []):
        rendered_segments.append(
            '<div class="segment">'
            f'<span class="timestamp">{html.escape(str(segment.get("start_text", "")))} → '
            f"{html.escape(str(segment.get('end_text', '')))}</span>"
            f'<span class="copy">{html.escape(str(segment.get("text", "")))}</span></div>'
        )
    st.markdown(
        f'<div class="transcript">{"".join(rendered_segments)}</div>', unsafe_allow_html=True
    )
    stem = Path(str(result.get("filename", "transcript"))).stem or "transcript"
    st.subheader("Downloads")
    downloads = [
        ("Combined JSON", combined_json(job), f"{stem}-combined.json", "application/json"),
        (
            "Meeting Notes Markdown",
            meeting_notes_markdown(job),
            f"{stem}-notes.md",
            "text/markdown",
        ),
        ("Transcript JSON", transcript_json(result), f"{stem}.json", "application/json"),
        ("Transcript Markdown", transcript_markdown(result), f"{stem}.md", "text/markdown"),
        ("TXT", transcript_txt(result), f"{stem}.txt", "text/plain"),
    ]
    for offset in range(0, len(downloads), 2):
        for column, (label, data, filename, mime) in zip(
            st.columns(2), downloads[offset : offset + 2], strict=False
        ):
            column.download_button(
                label,
                data,
                file_name=filename,
                mime=mime,
                use_container_width=True,
                key=f"download-{offset}-{filename}",
            )
    st.caption(f"Engine: {result.get('engine', 'unknown')}")


st.markdown('<div class="eyebrow">Audio and video → timestamped text</div>', unsafe_allow_html=True)
st.title("Meeting Notes & Action Tracker")
st.markdown(
    '<p class="lede">Turn a meeting recording into a clear summary, decisions, '
    "action items, and a timestamped transcript you can review or export.</p>",
    unsafe_allow_html=True,
)

health = get_health()
if health:
    mode_label = "Local Whisper" if health["mode"] == "local" else "Disabled demo mode"
    disclosure = (
        "Demo/local speech and analysis stay on the API host."
        if health.get("analysis_mode") != "live"
        else "Transcription stays on the API host; live analysis sends transcript text "
        "to the selected external provider."
    )
    st.markdown(
        '<div class="privacy">🔒 Source media is removed after the job finishes. '
        f"{disclosure} <strong>Mode:</strong> {mode_label} · "
        f"<strong>Upload limit:</strong> {health['max_upload_mb']} MB.</div>",
        unsafe_allow_html=True,
    )
    if health["mode"] != "local":
        st.error(
            "Real transcription is disabled because the API is running in demo mode. "
            "Set `TRANSCRIBER_MODE=local` and restart the API."
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
if uploaded:
    size_mb = len(uploaded.getvalue()) / (1024 * 1024)
    st.caption(f"Selected: {uploaded.name} · {size_mb:.2f} MB · {uploaded.type}")

st.subheader("2. Meeting analysis")
provider_labels = list(PROVIDERS)
configured_provider = health.get("analysis_provider") if health else None
default_provider_index = next(
    (
        index
        for index, label in enumerate(provider_labels)
        if PROVIDERS[label]["id"] == configured_provider
    ),
    0,
)
provider_label = st.selectbox(
    "Provider",
    provider_labels,
    index=default_provider_index,
    help="Provider credentials are loaded only by the backend.",
)
provider = PROVIDERS[provider_label]
model = st.selectbox("Model", provider["models"])
language = st.selectbox("Output language", LANGUAGES)
base_url = ""
protocol = "OpenAI-compatible"
if provider_label == "Custom":
    base_url = st.text_input("Provider base URL", placeholder="https://…")
if provider_label == "Custom":
    protocol = st.selectbox("Custom protocol", ["OpenAI-compatible", "Anthropic Messages"])
env_key_name = provider["env_key"]
st.caption(f"Credentials are loaded from server-side `{env_key_name}`.")
st.warning(
    "Live analysis sends transcript text to the selected external provider. "
    "A connection test or analysis request may incur provider cost."
)

if st.button(
    "Test connection",
    help="Runs one minimal request; live providers may charge for it.",
    disabled=not bool(health),
):
    if provider_label == "Custom" and not base_url.strip():
        st.error("Enter the provider base URL before testing the connection.")
    else:
        try:
            check = test_connection(
                _analysis_payload(provider_label, model, language, base_url, protocol)
            )
            if check.get("category") == "ok":
                st.success("Connection test succeeded.")
            else:
                st.error(f"Connection test: {check.get('category', 'provider_unavailable')}.")
        except (requests.RequestException, RuntimeError) as exc:
            st.error(str(exc))

st.subheader("3. Process")
can_start = bool(health and health.get("mode") == "local" and uploaded)
if st.button(
    "Start transcription and analysis",
    type="primary",
    use_container_width=True,
    disabled=not can_start,
):
    if provider_label == "Custom" and not base_url.strip():
        st.error("Enter the provider base URL for this provider.")
    else:
        try:
            filename, content, media_type = (
                uploaded.name,
                uploaded.getvalue(),
                uploaded.type or "application/octet-stream",
            )
            with st.status("Processing job…", expanded=True) as status:
                status_view = JobStatusView(status)
                job_id = submit_file(filename, content, media_type)
                session_job_ids = st.session_state.setdefault("session_job_ids", [])
                if job_id not in session_job_ids:
                    session_job_ids.append(job_id)
                status.write("Upload accepted; waiting for transcription…")
                job = poll_job(job_id, status_view)
                if job.get("transcription_status") == "completed":
                    status.write("Transcript complete; starting meeting analysis…")
                    payload = _analysis_payload(provider_label, model, language, base_url, protocol)
                    request_analysis(job_id, payload)
                    job = poll_job(job_id, status_view)
                st.session_state["active_job"] = job
                status.update(label=f"Job {job.get('status', 'finished')}", state="complete")
        except (requests.RequestException, RuntimeError, TimeoutError) as exc:
            st.error(str(exc))


def render_history() -> None:
    st.subheader("History")
    show_saved_jobs = st.toggle(
        "Show jobs from previous sessions",
        value=False,
        help="Saved jobs remain in SQLite until you explicitly delete them.",
    )
    try:
        response = requests.get(f"{API_URL}/jobs?limit=20", timeout=10)
        response.raise_for_status()
        jobs = response.json()
    except requests.RequestException:
        st.caption("History is unavailable while the API is offline.")
        return
    if not show_saved_jobs:
        session_job_ids = set(st.session_state.get("session_job_ids", []))
        jobs = visible_history_jobs(jobs, session_job_ids, include_saved=False)
    if not jobs:
        message = "No jobs in this browser session."
        if show_saved_jobs:
            message = "No saved jobs yet."
        st.caption(message)
        return
    for job in jobs:
        job_id = job.get("job_id", "")
        label = f"{job.get('filename', 'untitled')} · {job.get('status', 'unknown')}"
        left, right = st.columns([5, 1])
        if left.button(label, key=f"history-open-{job_id}", use_container_width=True):
            try:
                st.session_state["active_job"] = get_job(job_id)
                st.rerun()
            except (requests.RequestException, RuntimeError) as exc:
                st.error(str(exc))
        if right.button("Delete", key=f"history-delete-{job_id}", use_container_width=True):
            st.session_state["pending_delete_job_id"] = job_id
    pending = st.session_state.get("pending_delete_job_id")
    if pending:
        st.warning("Delete this completed job and its stored transcript? This cannot be undone.")
        confirm, cancel = st.columns(2)
        if confirm.button("Confirm delete", type="primary", key="confirm-delete"):
            try:
                response = requests.delete(f"{API_URL}/jobs/{pending}", timeout=10)
                if response.status_code >= 400:
                    st.error(_message(response, "The job could not be deleted."))
                else:
                    st.session_state.pop("pending_delete_job_id", None)
                    session_job_ids = st.session_state.get("session_job_ids", [])
                    if pending in session_job_ids:
                        session_job_ids.remove(pending)
                    if st.session_state.get("active_job", {}).get("job_id") == pending:
                        st.session_state.pop("active_job", None)
                    st.rerun()
            except requests.RequestException as exc:
                st.error(str(exc))
        if cancel.button("Cancel", key="cancel-delete"):
            st.session_state.pop("pending_delete_job_id", None)
            st.rerun()


active_job = st.session_state.get("active_job")
if isinstance(active_job, dict):
    st.divider()
    render_result(active_job)
    if st.button("Process another meeting", use_container_width=True, key="process-another"):
        st.session_state.pop("active_job", None)
        st.session_state.pop("pending_delete_job_id", None)
        st.rerun()
    if active_job.get("analysis_status") == "failed":
        st.caption("Retry uses the current provider settings and server-side credentials.")
        if st.button("Retry analysis with current settings", use_container_width=True):
            try:
                payload = _analysis_payload(provider_label, model, language, base_url, protocol)
                retry_analysis(active_job["job_id"], payload)
                st.session_state["active_job"] = poll_job(active_job["job_id"])
                st.rerun()
            except (requests.RequestException, RuntimeError, TimeoutError) as exc:
                st.error(str(exc))

render_history()
st.divider()
st.caption(
    "Speech recognition runs locally on the API host. Provider credentials are loaded "
    "only by the API server and are never included in job state or exports."
)
