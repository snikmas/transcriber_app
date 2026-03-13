# Transcriber
 check this
A FastAPI service that transcribes audio/video files and YouTube videos, with a Streamlit UI.

## What it does

- Accepts a file upload (audio/video) or a YouTube URL via `POST /transcribe`
- Creates a background job and returns a job ID
- Worker processes the job: extracts audio from video if needed, then transcribes
- Poll `GET /transcribe/{job_id}` to check status and get the result

**Files:** uses faster-whisper (offline, CPU) to transcribe locally
**YouTube URLs:** fetches subtitles via `youtube-transcript-api`

## Stack

- FastAPI + threading (single background worker queue)
- faster-whisper (tiny model, CPU, int8)
- ffmpeg for audio extraction from video
- yt-dlp + youtube-transcript-api for YouTube subtitles
- SQLite for job persistence
- Streamlit UI

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/transcribe` | Submit a file or URL, returns `jobs_id` |
| `GET` | `/transcribe/{job_id}` | Poll job status / get result |
| `GET` | `/jobs` | List all jobs |
| `DELETE` | `/jobs/{job_id}` | Delete a job |

### POST /transcribe

Send either a file:
```
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
{ "message": "is queued" }
```

On failure:
```json
{ "message": "the process is failed" }
```
 check 
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

## UI

Run the API first, then the UI:

```bash
uvicorn main:app --reload
streamlit run ui/app.py
```

The UI polls the job until complete, then displays the transcript with stats (duration, segments, word count, language) and download buttons for TXT, JSON, and Markdown.

## Project structure

```
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
