# Private Local Transcriber

A FastAPI and Streamlit application that turns uploaded audio or video into a
timestamped transcript with durable job tracking and TXT, JSON, and Markdown
exports.

The repository starts in an explicitly labeled deterministic demo mode, so a
reviewer can inspect the complete workflow without downloading an ML model.
Local mode runs actual speech recognition with faster-whisper.

![Private Local Transcriber](assets/transcriber-result.png)

## What it demonstrates

- Bounded audio/video upload intake
- Durable asynchronous jobs backed by SQLite
- Background transcription without blocking the API request
- Lazy local Whisper model loading
- Timestamped transcript rendering
- TXT, JSON, and Markdown exports
- Restart recovery and temporary-file cleanup
- Docker Compose and portable CI

## Try the instant demo

Python 3.12 is the supported runtime.

```bash
git clone https://github.com/snikmas/transcriber_app.git
cd transcriber_app
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .

# terminal 1
uvicorn main:app

# terminal 2
streamlit run ui/app.py
```

Open `http://localhost:8501`, select **Use the bundled demo audio fixture**, and
start transcription.

Demo mode returns a fixed fictional transcript. It exists to demonstrate upload,
job persistence, polling, rendering, and exports without a model download. It
does not claim to recognize the fixture's audio.

## Run real local transcription

Install the faster-whisper extra and make sure `ffmpeg` is available:

```bash
pip install -e ".[local]"
export TRANSCRIBER_MODE=local
uvicorn main:app
```

The default `tiny` model downloads on the first local-mode job and is reused
afterward. The first request can therefore take longer. For a fully offline
runtime after caching the model:

```bash
export WHISPER_OFFLINE=true
```

CPU and `int8` are safe defaults. Accuracy and processing time depend on the
chosen model, hardware, audio quality, language, and recording length.

## Docker

The Compose default is the same deterministic demo:

```bash
docker compose up --build
```

Run actual Whisper locally through Docker:

```bash
TRANSCRIBER_MODE=local docker compose up --build
```

Compose persists the SQLite database and Hugging Face model cache in named
volumes. Uploaded media is deleted after each terminal job state.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Mode, model readiness, and upload limit |
| `POST` | `/transcribe` | Submit one audio/video file |
| `GET` | `/transcribe/{job_id}` | Read status, error, or completed result |
| `GET` | `/jobs` | List recent durable jobs |
| `DELETE` | `/jobs/{job_id}` | Delete job metadata and remaining temp media |

Submit:

```bash
curl -F "file=@meeting.mp3" http://localhost:8000/transcribe
```

Accepted response:

```json
{
  "job_id": "16d6f30d-6ee2-4477-9e0b-349fd55e8736",
  "status": "queued",
  "status_url": "/transcribe/16d6f30d-6ee2-4477-9e0b-349fd55e8736"
}
```

Jobs move through `queued → processing → completed|failed`. Completed results
include normalized seconds, display timestamps, full text, segment text,
language confidence, word count, and the engine used.

Interactive API documentation is available at `http://localhost:8000/docs`.

## Configuration

Copy [.env.example](.env.example) if you want custom settings.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TRANSCRIBER_MODE` | `demo` | `demo` or actual `local` inference |
| `WHISPER_MODEL` | `tiny` | faster-whisper model name |
| `WHISPER_DEVICE` | `cpu` | Inference device |
| `WHISPER_COMPUTE_TYPE` | `int8` | CTranslate2 compute type |
| `WHISPER_OFFLINE` | `false` | Require already-cached model files |
| `DATABASE_PATH` | `data/jobs.sqlite3` | Durable SQLite location |
| `UPLOAD_DIR` | `data/uploads` | Unique temporary job directories |
| `MAX_UPLOAD_MB` | `100` | Streaming upload limit |
| `API_URL` | `http://localhost:8000` | Streamlit-to-API address |

## Architecture

```text
Streamlit / API client
        ↓ multipart upload
FastAPI bounded file intake
        ↓ queued job
SQLite repository + in-process queue
        ↓
single background worker
        ↓
demo engine OR lazy faster-whisper + ffmpeg
        ↓
persisted transcript / error
        ↓
polling UI + TXT / JSON / Markdown exports
```

See [Architecture](docs/ARCHITECTURE.md) and [Privacy and
limitations](docs/PRIVACY.md).

## Verification

The fast suite never downloads a model or uses personal files:

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
docker compose config --quiet
```

## What can be customized for a client

- Different Whisper models, languages, and hardware targets
- Speaker diarization and subtitle formats
- Batch uploads and retention policies
- Summaries or action items through a chosen LLM provider
- Authentication, cloud storage, and distributed workers
- Branded UI, deployment, and monitoring

## Honest limitations

- The release uses one in-process worker, not a distributed queue.
- Local inference performance depends heavily on the machine.
- SQLite is appropriate for the local/small-team demo, not large-scale SaaS.
- YouTube extraction is intentionally postponed because it is externally fragile.
- Public hosted inference is not included.
- Transcription accuracy is not guaranteed.

## License

MIT. See [LICENSE](LICENSE).
