import json
import html as _html
import streamlit as st
import requests
import time

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Transcriber",
    page_icon="🎙️",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* ── Root ── */
:root {
    --bg:        #0d0e11;
    --surface:   #14161b;
    --border:    #272a32;
    --accent:    #e8ff47;
    --accent-dim:#b8cc2e;
    --text:      #e4e6ed;
    --muted:     #5a5f72;
    --success:   #3dffa0;
    --error:     #ff4b6e;
    --warning:   #ffb347;
}

/* ── Base resets ── */
html, body, [class*="css"], [class*="st-emotion-cache"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
}

/* ── Hide default streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 720px !important; }

/* ── Headings ── */
h1, h2, h3 {
    font-family: 'IBM Plex Mono', monospace !important;
    letter-spacing: -0.02em;
}

/* ── Reduce Streamlit's default vertical gap ── */
[data-testid="stVerticalBlock"] {
    gap: 0.4rem !important;
}

/* ── Divider ── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1rem 0 !important;
}

/* ── Custom label override (mono, small, muted) ── */
label,
[data-testid="stFileUploader"] label p,
[data-testid="stTextInput"] label p {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--muted) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] section {
    background: var(--surface) !important;
    border: 1px dashed var(--border) !important;
    border-radius: 4px !important;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"] section:hover {
    border-color: var(--accent) !important;
}
[data-testid="stFileUploaderDeleteBtn"] {
    color: var(--muted) !important;
}

/* ── Text input ── */
[data-testid="stTextInput"] input {
    backgro und: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.85rem !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(232,255,71,0.12) !important;
}

/* ── Checkboxes ── */
[data-testid="stCheckbox"] span {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
    color: var(--text) !important;
}
[data-testid="stCheckbox"] div[data-baseweb="checkbox"] div {
    border-color: var(--border) !important;
    border-width: 1px !important;
    border-radius: 2px !important;
}

/* ── Primary button ── */
[data-testid="baseButton-primary"] {
    background: var(--accent) !important;
    color: #0d0e11 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: 3px !important;
    padding: 0.6rem 1.4rem !important;
    transition: background 0.15s, transform 0.1s;
}
[data-testid="baseButton-primary"]:hover { background: var(--accent-dim) !important; }
[data-testid="baseButton-primary"]:active { transform: scale(0.98) !important; }
[data-testid="baseButton-primary"]:disabled {
    background: var(--surface) !important;
    color: var(--muted) !important;
    border: 1px solid var(--border) !important;
}

/* ── Secondary / download buttons ── */
[data-testid="baseButton-secondary"],
[data-testid="stDownloadButton"] button {
    background: transparent !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
    transition: border-color 0.15s, color 0.15s;
}
[data-testid="baseButton-secondary"]:hover,
[data-testid="stDownloadButton"] button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}

/* ── Expander (transcript viewer) ── */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}
[data-testid="stExpander"] summary {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--muted) !important;
}
[data-testid="stExpander"] summary:hover {
    color: var(--text) !important;
}
[data-testid="stExpander"] svg {
    fill: var(--muted) !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] p {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
    color: var(--muted) !important;
}

/* ── Alert / notification boxes (dark theme override) ── */
[data-testid="stAlert"],
[data-testid="stAlert"] > div,
[data-testid="stAlert"] > div > div {
    background: var(--surface) !important;
    background-color: var(--surface) !important;
}
[data-testid="stAlert"] {
    border: 1px solid var(--border) !important;
    border-left: 3px solid var(--muted) !important;
    border-radius: 3px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
    color: var(--text) !important;
}
[data-testid="stAlert"] p,
[data-testid="stAlert"] span {
    color: var(--text) !important;
    font-family: 'IBM Plex Mono', monospace !important;
}
[data-testid="stAlert"] svg {
    flex-shrink: 0;
}

/* ── JSON viewer (inside expander) ── */
[data-testid="stJson"] {
    background: #0a0b0e !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}
[data-testid="stJson"] * {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.76rem !important;
}

/* ── Scrollable transcript box ── */
.transcript-box {
    background: #0a0b0e;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1.2rem 1.4rem;
    max-height: 320px;
    overflow-y: auto;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    line-height: 1.8;
    color: var(--text);
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
}
.transcript-box::-webkit-scrollbar { width: 4px; }
.transcript-box::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 2px;
}
.transcript-line { display: flex; gap: 1rem; margin-bottom: 0.4rem; }
.transcript-ts {
    color: var(--accent);
    white-space: nowrap;
    flex-shrink: 0;
    font-size: 0.72rem;
    padding-top: 0.05rem;
}
.transcript-text { color: var(--text); }

/* ── Section labels ── */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--muted);
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* ── OR divider ── */
.or-divider {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 1.2rem 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: var(--muted);
    letter-spacing: 0.1em;
}
.or-divider::before, .or-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* ── Stat pills ── */
.stats-row {
    display: flex;
    gap: 1.5rem;
    margin: 1rem 0;
    padding: 0.9rem 1.2rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
}
.stat-item { display: flex; flex-direction: column; gap: 0.2rem; }
.stat-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--accent);
}
.stat-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.63rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
}
</style>
""", unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom: 0.2rem;">
    <span style="font-family:'IBM Plex Mono',monospace; font-size:0.72rem;
                 text-transform:uppercase; letter-spacing:0.14em; color:#5a5f72;">
        ◼ v0.1 — audio / video → text
    </span>
</div>
""", unsafe_allow_html=True)

st.title("Transcriber")

st.markdown("""
<p style="font-family:'IBM Plex Sans',sans-serif; font-size:0.95rem;
           color:#5a5f72; margin-top:-0.4rem; margin-bottom:1.8rem;
           font-weight:300; line-height:1.6;">
Upload a local file or paste a YouTube URL.<br>
Get a timestamped transcript — download in the format you need.
</p>
""", unsafe_allow_html=True)

st.divider()


# ── Input section ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">01 — Input</div>', unsafe_allow_html=True)

data = st.file_uploader(
    label="Drop audio or video file",
    type=["mp3", "mp4", "wav", "m4a", "ogg", "webm", "mkv"],
    help="Supported: mp3, mp4, wav, m4a, ogg, webm, mkv — max 500 MB"
)

st.markdown('<div class="or-divider">or</div>', unsafe_allow_html=True)

url_video = st.text_input(
    label="YouTube URL",
    placeholder="https://www.youtube.com/watch?v=...",
)

# Reset result when input changes
_input_sig = (data.name if data else "", url_video.strip())
if st.session_state.get("_input_sig") != _input_sig and st.session_state.get("show_result"):
    st.session_state["show_result"] = False
if data or url_video.strip():
    st.session_state["_input_sig"] = _input_sig


# ── Options section ────────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="section-label">02 — Output format</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    fmt_txt  = st.checkbox("TXT",      value=True)
with col2:
    fmt_json = st.checkbox("JSON")
with col3:
    fmt_md   = st.checkbox("Markdown")

st.markdown("<div style='margin-top:0.3rem'></div>", unsafe_allow_html=True)


# ── Submit ─────────────────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="section-label">03 — Run</div>', unsafe_allow_html=True)

has_input = bool(data) or bool(url_video.strip())

transcribe_btn = st.button(
    "⚡  Get Transcript",
    type="primary",
    disabled=not has_input,
    use_container_width=True,
    help="Upload a file or paste a URL first" if not has_input else None,
)

if not has_input:
    st.markdown("""
    <p style="font-family:'IBM Plex Mono',monospace; font-size:0.72rem;
               color:#5a5f72; margin-top:0.5rem; text-align:center;">
        ↑ add a file or URL to enable
    </p>
    """, unsafe_allow_html=True)


# ── Simulated result (shown when button is pressed) ───────────────────────────
MOCK_TRANSCRIPT = [
    ("00:00:00", "00:00:04", "Welcome to the lecture on distributed systems."),
    ("00:00:04", "00:00:09", "Today we'll cover the CAP theorem and its practical implications."),
    ("00:00:09", "00:00:15", "The CAP theorem states that a distributed system can only guarantee two out of three properties:"),
    ("00:00:15", "00:00:20", "consistency, availability, and partition tolerance."),
    ("00:00:20", "00:00:27", "Let's start with consistency — every read receives the most recent write or an error."),
    ("00:00:27", "00:00:34", "Availability means every request receives a non-error response, though it may not be the latest."),
    ("00:00:34", "00:00:41", "Partition tolerance: the system continues to operate despite network partitions between nodes."),
    ("00:00:41", "00:00:49", "In practice, partition tolerance is non-negotiable in real distributed environments."),
    ("00:00:49", "00:00:56", "So the real tradeoff is between consistency and availability when partitions occur."),
    ("00:00:56", "00:01:04", "Systems like Cassandra choose availability — you get eventual consistency instead."),
    ("00:01:04", "00:01:11", "Systems like HBase choose consistency — you may get errors during a partition."),
    ("00:01:11", "00:01:19", "Understanding your system's requirements determines which tradeoff is acceptable."),
]

if transcribe_btn or st.session_state.get("show_result"):
    st.session_state["show_result"] = True

    st.divider()

    with st.spinner("Transcribing..."):
        if not st.session_state.get("job_id"):
            # no job yet — submit
            if data:
                response = requests.post('http://localhost:8000/transcribe', files={"file": (data.name, data, data.type)})
            else:
                response = requests.post('http://localhost:8000/transcribe', json={"url": url_video.strip()})
            st.session_state["job_id"] = response.json()["job_id"]
            time.sleep(3)
            st.rerun()
        else:
            # job exists — check status
            job_id = st.session_state["job_id"]
            response = requests.get(f'http://localhost:8000/jobs/{job_id}')
            status = response.json()["status"]

            if status == "processing" or status == "queued":
                time.sleep(3)
                st.rerun()
            elif status == "failed":
                st.session_state.pop("job_id", None)
                st.error("Transcription failed.")
                st.stop()
            # if "done" — fall through, show result below

    st.success("✓  Transcript ready")

    # ── Stats bar ──────────────────────────────────────────────────────────
    st.markdown("""
    <div class="stats-row">
        <div class="stat-item">
            <span class="stat-value">01:19</span>
            <span class="stat-label">Duration</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">12</span>
            <span class="stat-label">Segments</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">148</span>
            <span class="stat-label">Words</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">en</span>
            <span class="stat-label">Language</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Transcript viewer ──────────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:1.2rem">04 — Transcript</div>',
                unsafe_allow_html=True)

    lines_html = ""
    for start, end, text in MOCK_TRANSCRIPT:
        safe_text = _html.escape(text)
        lines_html += f"""
        <div class="transcript-line">
            <span class="transcript-ts">[{start} → {end}]</span>
            <span class="transcript-text">{safe_text}</span>
        </div>"""

    st.markdown(f'<div class="transcript-box">{lines_html}</div>', unsafe_allow_html=True)

    st.markdown("""
    <p style="font-family:'IBM Plex Mono',monospace; font-size:0.65rem;
               color:#5a5f72; margin-top:0.4rem;">
        scroll to read · max 320px height
    </p>
    """, unsafe_allow_html=True)

    # ── Download section ───────────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:1.4rem">05 — Download</div>',
                unsafe_allow_html=True)

    mock_txt  = "\n".join(
        f"[{s} → {e}]  {t}" for s, e, t in MOCK_TRANSCRIPT
    )
    mock_json = json.dumps(
        [{"start": s, "end": e, "text": t} for s, e, t in MOCK_TRANSCRIPT],
        ensure_ascii=False, indent=2
    )
    mock_md   = "\n".join(
        f"**[{s} → {e}]** {t}" for s, e, t in MOCK_TRANSCRIPT
    )

    selected_formats = []
    if fmt_txt:  selected_formats.append(("TXT",      mock_txt,  "transcript.txt",  "text/plain"))
    if fmt_json: selected_formats.append(("JSON",     mock_json, "transcript.json", "application/json"))
    if fmt_md:   selected_formats.append(("Markdown", mock_md,   "transcript.md",   "text/markdown"))

    if not selected_formats:
        st.warning("Select at least one output format above.")
    else:
        dl_cols = st.columns(len(selected_formats))
        for col, (label, content, fname, mime) in zip(dl_cols, selected_formats):
            with col:
                st.download_button(
                    label=f"↓  {label}",
                    data=content,
                    file_name=fname,
                    mime=mime,
                    use_container_width=True,
                )

    # ── Expander: raw view ─────────────────────────────────────────────────
    with st.expander("▸  Raw JSON output"):
        st.json([{"start": s, "end": e, "text": t} for s, e, t in MOCK_TRANSCRIPT])


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:3rem; padding-top:1.2rem;
            border-top:1px solid #272a32;
            font-family:'IBM Plex Mono',monospace;
            font-size:0.65rem; color:#2e3140;
            display:flex; justify-content:space-between;">
    <span>transcriber · local</span>
    <span>powered by whisper</span>
</div>
""", unsafe_allow_html=True)
