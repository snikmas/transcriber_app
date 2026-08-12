# Release notes

## Portfolio release

The prototype has been rebuilt around one honest buyer journey: upload a local
audio/video file, follow its durable background job, review a timestamped
transcript and structured meeting notes, and export both.

### Product

- Upload-only release surface; fragile YouTube extraction is postponed
- Explicit deterministic demo mode that works without model downloads
- Actual local faster-whisper mode with lazy one-time model loading
- Timestamped transcript, metadata, TXT/JSON/Markdown/SRT exports, and combined
  meeting-notes JSON/Markdown exports
- Meeting analysis lifecycle with summary, decisions, action items, open
  questions, follow-ups, schema validation, partial-success preservation, and
  retry without retranscription
- Provider-neutral Demo, OpenAI, Anthropic, OpenRouter, DeepSeek, and custom
  OpenAI/Anthropic-compatible adapters
- Clear local/private-processing and engine-mode labels

### Reliability

- Stable `job_id` API contract and typed FastAPI responses
- SQLite as the durable source of truth for status, errors, and results
- Restart recovery for interrupted jobs
- Bounded streaming uploads, sanitized names, and unique job directories
- Temporary media cleanup on both success and failure
- Configurable database, upload path, model, device, compute type, and limits
- Backend-only provider keys are excluded from public requests, job state,
  responses, exports, and logs; custom provider URLs have an explicit
  private-destination policy

### Delivery

- Python 3.12 runtime and Docker Compose configuration
- Portable offline test suite and GitHub Actions
- Fictional repository-owned demo fixture, screenshots, and public documentation

### Known boundaries

- One in-process worker and SQLite are suitable for a local/small-team demo, not
  a distributed multi-tenant service.
- Authentication, retention automation, diarization, real-time capture,
  automatic redaction, and hosted guarantees remain future adaptations.
- Live provider calls are externally dependent and may incur cost; review
  sensitive-data requirements before enabling them.
