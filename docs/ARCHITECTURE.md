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

### Two-stage in-process queues

`src/worker.py` runs one daemon worker thread that polls transcription and
analysis queues. This is intentional for a local/private product demonstration.
Queue entries contain only durable job IDs; credentials and prompts never cross
the queue boundary. The worker changes durable state before and after each
stage and removes each job's media directory in a `finally` block.

### Transcription engines

`src/transcriber.py` has a production engine and a test engine:

- `local`: the product default, with lazy faster-whisper loading and actual inference
- `demo`: deterministic fictional output retained only for offline automated tests

Video files are converted to 16 kHz mono WAV with `ffmpeg` inside their isolated
job directory. Audio files go directly to the engine.

### Meeting analysis

After transcription reaches `completed`, `src/analysis/service.py` chunks the
timestamped transcript, asks a provider for evidence-only extraction, performs
one bounded synthesis/repair path, and validates the final object with the
Pydantic contract in `src/analysis/schemas.py`. The persisted analysis row is
separate from the authoritative transcript, so provider/schema failure becomes
`partial_success` and can be retried without retranscription.

`src/analysis/providers.py` normalizes Demo, OpenAI Responses, Anthropic
Messages, OpenRouter, DeepSeek, and custom OpenAI/Anthropic-compatible calls.
`src/analysis/urls.py` rejects unsafe custom destinations. Provider credentials
are resolved only from the API server environment and never enter public
requests, SQLite, responses, exports, or logs. DeepSeek uses its fixed official
endpoint; custom URLs pass through the SSRF guard before a request is sent.

### Streamlit client

`ui/app.py` checks API health, identifies the active engine mode, submits the
upload, lets the user choose a provider/model/language, polls both stages,
renders escaped meeting notes and timestamped segments, exposes history/delete,
and creates combined JSON, Meeting Notes Markdown, transcript JSON, TXT, and SRT
downloads from the normalized result.

### Lifecycle and recovery

SQLite is the source of truth. Startup marks queued/processing transcription and
analysis rows as failed with an interruption message, then removes abandoned
upload directories. Terminal deletion cascades the analysis row; active jobs
return `409` and are not deleted.

## Production upgrade path

For larger deployments, replace the in-process queues with Redis/RQ, Celery, or
a managed task service; move media to object storage; use PostgreSQL; add
authentication, retention jobs, observability, worker autoscaling, and an
explicit policy for external provider transcript transfer.
