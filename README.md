# Transcriber

FastAPI service that transcribes uploaded audio/video files locally with faster-whisper, plus a small Streamlit UI.

**Portfolio demo of:** async jobs, file upload API, worker queue, SQLite persistence, local ML inference, simple frontend.

> File upload transcription works. YouTube URL mode is temporarily unreliable because YouTube often blocks subtitle API calls from non-residential IPs.

## What it does

- Accepts a file upload (audio/video) via `POST /transcribe`
- Optionally accepts a YouTube URL (best-effort; may fail off residential networks)
- Creates a background job and returns a job ID
- Worker extracts audio if needed, then transcribes
- Client polls `GET /transcribe/{job_id}` for status/result
- Streamlit UI can download transcript as TXT, JSON, or Markdown

## Stack

- FastAPI + background worker thread
- faster-whisper (tiny model, CPU, int8) for local offline file transcription
- ffmpeg for audio extraction from video
- yt-dlp + youtube-transcript-api for YouTube path
- SQLite for job persistence
- Streamlit UI

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/transcribe` | Submit a file or URL, returns `job_id` |
| `GET` | `/transcribe/{job_id}` | Poll job status / get result |
| `GET` | `/jobs` | List all jobs |
| `DELETE` | `/jobs/{job_id}` | Delete a job |

### POST /transcribe

Send a file:

```text
multipart/form-data  →  file=<upload>
```

Or a URL:

```json
{ "url": "https://www.youtube.com/watch?v=..." }
```

Set `X-Source: ui` header to identify requests from the UI. CLI tools (curl, python-requests, Postman) are detected automatically via User-Agent.

### GET /transcribe/{job_id}

While processing:

```json
{ "message": "in process..." }
```

```json
{ "message": "is queued" }
```

On failure:

```json
{ "message": "the process is failed" }
```

On success:

```json
{
  "result": {
    "filename": "audio.mp3",
    "duration": "00:01:19",
    "language": "EN",
    "language Probability": "97.0%",
    "transcript": [
      { "start_t": "00:00:00", "end_t": "00:00:04", "content": "..." }
    ]
  }
}
```

YouTube results return only `transcript` (no filename/duration/language).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# terminal 1 — API
uvicorn main:app --reload

# terminal 2 — UI
streamlit run ui/app.py
```

Optional Docker:

```bash
docker compose up --build
```

The UI polls the job until complete, then shows transcript stats (duration, segments, word count, language) and download buttons.

## Project structure

```text
main.py              — FastAPI app, route definitions
src/
  worker.py          — background thread, processes jobs from queue
  jobs.py            — in-memory job store + queue
  parsers.py         — Whisper result → dict, file save helpers
  transcriber.py     — faster-whisper wrapper
  utils.py           — time formatting, URL parsing
  constants.py       — enums, allowed types, client lists
  database/          — SQLite persistence
extractor.py         — ffmpeg audio extraction, yt-dlp, YouTube API
ui/
  app.py             — Streamlit frontend
```

## Hire / reuse note

Useful reference if you need a small media → text backend, local speech-to-text prototype, or async job API pattern in Python.
