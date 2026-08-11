# Developer summary

This note describes the implemented portfolio release. It is intentionally
more concrete than the buyer-facing README: names below are current module and
endpoint boundaries, not a future architecture promise.

## Architecture

```text
Streamlit UI (ui/app.py)
  ├─ POST /transcribe ──────────────┐
  ├─ poll GET /jobs/{id}             │
  └─ POST /jobs/{id}/analysis       │
                                      ▼
FastAPI (main.py) → SQLite (src/database/database.py)
                    ↘ transcription queue ─┐
                    ↘ analysis queue ──────┤
                                             ▼
                                   one daemon worker (src/worker.py)
                                      ├─ demo/local transcription
                                      └─ meeting analysis provider
```

The API writes uploads in a per-job directory, records a durable queued job,
and returns `202` with a stable `job_id`. The worker persists each lifecycle
transition. Transcription is authoritative; analysis is a separate row and may
end in `partial_success` without removing a good transcript.

## Important files

| File | Responsibility |
| --- | --- |
| `main.py` | FastAPI app, request models, upload boundary, lifecycle routes, provider selection |
| `ui/app.py` | Streamlit upload, provider controls, polling, history, notes, and downloads |
| `src/config.py` | Environment settings, bounded analysis limits, provider-key lookup |
| `src/transcriber.py` | Deterministic Demo engine, lazy `faster-whisper`, video-to-WAV preparation |
| `src/jobs.py` | Durable job and analysis queue handoff |
| `src/worker.py` | Transcription/analysis execution, state updates, safe media cleanup |
| `src/database/database.py` | SQLite schema/migration, status composition, redacted errors, cascade delete |
| `src/analysis/schemas.py` | Pydantic MeetingAnalysis contract and timestamp evidence |
| `src/analysis/service.py` | Chunking, bounded retries, synthesis, schema-validation boundary |
| `src/analysis/providers.py` | Demo, OpenAI, Anthropic, OpenRouter, PackyAPI, and custom adapters |
| `src/analysis/urls.py` | HTTPS/custom URL and private-destination checks |
| `src/analysis/secrets.py` | One-time in-memory credential leases (no SQLite persistence) |
| `src/exports.py` | TXT, JSON, SRT, combined JSON, and Meeting Notes Markdown serializers |
| `samples/meeting_fixture.py` | Fictional transcript/analysis data used by offline tests |
| `compose.yaml` / `Dockerfile` | API/UI services, health dependency, data/model volumes, ffmpeg runtime |

## Lifecycle

1. `POST /transcribe` validates extension and media type, streams at most
   `MAX_UPLOAD_MB`, sanitizes the display name, writes `data/uploads/<job_id>`,
   and inserts a queued SQLite row.
2. The worker marks transcription `processing`, runs Demo or local Whisper
   (video is converted with `ffmpeg`), then stores normalized segments and
   metadata or a bounded failure.
3. `POST /jobs/{id}/analysis` creates one analysis row and queues only the job
   ID. Duplicate requests observe the existing row; retry resets only analysis.
4. The analysis service chunks transcript text, calls the selected provider,
   parses/repairs once at the schema boundary, and stores validated JSON plus
   non-secret metadata.
5. `GET /jobs/{id}` composes overall status. Failed analysis yields
   `partial_success`; the transcript remains readable and exportable.
6. The worker removes only the canonical per-job upload directory. On startup,
   queued/processing rows are marked failed with an interruption message.
   Terminal jobs can be deleted; active jobs return `409`.

## API contract

- `GET /health` reports mode, model readiness, upload limit, analysis mode,
  provider, protocol, and configuration readiness. It never reports key values.
- `POST /transcribe` accepts multipart field `file` and returns
  `{job_id, status, status_url}` with HTTP `202`.
- `GET /transcribe/{job_id}` and `GET /jobs/{job_id}` return the public job,
  transcript result, transcription/analysis statuses, and public analysis
  metadata. Internal paths, prompts, raw provider payloads, and secrets are
  filtered.
- `GET /jobs?limit=20` lists recent jobs; limit is clamped to 1–100.
- `POST /jobs/{id}/analysis` and `/transcribe/{id}/analysis` queue analysis;
  `GET` on the same path reads it. `/analysis/retry` retries without
  retranscription.
- `DELETE /jobs/{id}` removes a terminal job and cascades its analysis.

## Providers and configuration

`ANALYSIS_MODE=demo` and `ANALYSIS_PROVIDER=demo` are safe defaults. The UI can
submit a provider, model, output language, base URL, and one-time key per
request. Environment-driven live defaults use `ANALYSIS_MODE=live` and one of
the supported provider keys:

- `openai` → OpenAI Responses API (`OPENAI_API_KEY`)
- `anthropic` → Anthropic Messages API (`ANTHROPIC_API_KEY`)
- `openrouter` → OpenAI-compatible chat (`OPENROUTER_API_KEY`)
- `packyapi` → OpenAI-compatible chat (`PACKYAPI_API_KEY` plus
  `ANALYSIS_BASE_URL`, because the endpoint is account-specific)
- `custom_openai` or `custom_anthropic` → explicit custom URL and protocol

`ANALYSIS_TIMEOUT_SECONDS`, `ANALYSIS_MAX_ATTEMPTS`, `ANALYSIS_CHUNK_CHARS`,
`ANALYSIS_MAX_CHUNKS`, and `ANALYSIS_MAX_TRANSCRIPT_CHARS` are bounded at load
time. Custom URL validation blocks private/reserved destinations unless
`ALLOW_LOCAL_PROVIDER_URLS=true` is an explicit local-service opt-in.

## Secret and data boundary

Provider keys are accepted either from environment or a one-time request body.
Request keys are used while constructing the provider and are not placed in the
job queue, SQLite rows, public responses, or exports. Error persistence uses a
safe allowlist/fallback; logs deliberately record only error type/lifecycle.
External providers receive transcript text. Demo and local Whisper keep the
transcript on the API host, but local model downloads may contact Hugging Face
unless the model is already cached/offline mode is enabled. Uploaded media is
temporary; transcript/analysis JSON remains in SQLite until deletion.

## Commands and verification

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
docker compose config --quiet
git diff --check
```

For the no-key path, run `uvicorn main:app` and `streamlit run ui/app.py`, then
select the bundled fixture and Demo provider. For local inference install
`pip install -e ".[local]"` and ensure `ffmpeg` is available. Compose starts the
API and UI with a health-gated dependency and named volumes for SQLite/model
cache.

## Tests

The test suite is offline and currently contains 65 test functions plus
parameterized cases. It exercises upload validation/limits, cleanup and restart
recovery, SQLite migration and deletion, Demo output, video preparation,
analysis schemas/parsing/chunking, provider response/error redaction and URL
safety, one-time secret leases, partial-success/retry, API routes, and every
transcript/combined export format. No test requires a model download, provider
credential, network call, or personal recording.

## Extension points

Add a provider by implementing the normalized `AnalysisProvider.generate`
contract and wiring it in `provider_from_config`. Add an analysis profile by
defining a Pydantic schema/prompt/service boundary rather than changing job
storage. Replace the queue/repository seams with Redis/RQ/Celery and
PostgreSQL/object storage for a hosted deployment. Add authentication,
retention, audit events, webhooks, CRM/task integrations, GPU packaging, or a
branded UI at those boundaries while preserving the upload and polling API.
