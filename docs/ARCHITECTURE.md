# Architecture

## Components

### FastAPI intake

`main.py` validates the file extension and media type, streams data in one
megabyte chunks, enforces the configured size limit during the write, sanitizes
the display filename, and creates an isolated directory for every job.

### Durable repository

`src/database/database.py` stores job identity, state, timestamps, result JSON,
and bounded failure details in SQLite. Reads use SQLite as the source of truth.
On startup, abandoned queued or processing jobs are marked failed with an
interruption explanation.

### In-process queue

`src/worker.py` runs one daemon worker thread. This is intentional for a
local/private product demonstration. The thread changes durable state before and
after inference and removes each job's media directory in a `finally` block.

### Transcription engines

`src/transcriber.py` has two modes:

- `demo`: deterministic fictional output with no model dependency
- `local`: lazy faster-whisper model loading and actual inference

Video files are converted to 16 kHz mono WAV with `ffmpeg` inside their isolated
job directory. Audio files go directly to the engine.

### Streamlit client

`ui/app.py` checks API health, identifies the active engine mode, submits the
upload, polls the durable job, renders escaped timestamped segments, and creates
three downloads from the normalized result.

## Production upgrade path

For larger deployments, replace the in-process queue with Redis/RQ, Celery, or a
managed task service; move media to object storage; use PostgreSQL; add
authentication, retention jobs, observability, and worker autoscaling.
