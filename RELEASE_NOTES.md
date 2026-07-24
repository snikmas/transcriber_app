# Release notes

## Portfolio release

The prototype has been rebuilt around one honest buyer journey: upload a local
audio/video file, follow its durable background job, review a timestamped
transcript, and export it.

### Product

- Upload-only release surface; fragile YouTube extraction is postponed
- Explicit deterministic demo mode that works without model downloads
- Actual local faster-whisper mode with lazy one-time model loading
- Timestamped transcript, metadata, and TXT/JSON/Markdown exports
- Clear local/private-processing and engine-mode labels

### Reliability

- Stable `job_id` API contract and typed FastAPI responses
- SQLite as the durable source of truth for status, errors, and results
- Restart recovery for interrupted jobs
- Bounded streaming uploads, sanitized names, and unique job directories
- Temporary media cleanup on both success and failure
- Configurable database, upload path, model, device, compute type, and limits

### Delivery

- Python 3.12 runtime and Docker Compose configuration
- Portable mocked test suite and GitHub Actions
- Fictional repository-owned demo fixture, screenshots, and public documentation
