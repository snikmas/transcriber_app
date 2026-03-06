# Transcriber

A FastAPI service that transcribes audio/video files and YouTube videos.

## What it does

- Accepts a file upload (audio/video) or a YouTube URL via `POST /transcribe`
- Creates a background job, returns a job ID
- Worker processes the job: extracts audio if needed, then transcribes
- Poll `GET /transcribe/{job_id}` to get the result

**Files:** uses Whisper (HuggingFace, offline) to transcribe locally
**YouTube URLs:** fetches subtitles via `youtube-transcript-api`, falls back to download + transcribe

Response shape differs by client:
- CLI → JSON with `content` + `download_url`
- Browser → JSON with `content` (file download planned)

## Stack

- FastAPI + threading (single background worker queue)
- Whisper model (offline, HuggingFace)
- ffmpeg for audio extraction from video
- yt-dlp + youtube-transcript-api for YouTube
- YouTube Data API v3 for video metadata (title, language, duration)

## Current state

- File upload flow works end-to-end
- YouTube URL flow: subtitle fetching works, not yet integrated into job result
- `get_video_info()` implemented but not wired into the worker yet
- Browser vs CLI response handling is partially done

## Planned

- Wire YouTube metadata (title, language, duration) into the job
- Return subtitle/transcription result for YouTube jobs
- Browser response: serve a ready-to-download file
- Fallback: if no subtitles exist, download audio and run Whisper
