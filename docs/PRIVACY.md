# Privacy and limitations

## Local data behavior

- Uploaded bytes are written to a unique job directory.
- The worker deletes that directory after completion or failure.
- Job metadata, status, errors, and transcript JSON remain in SQLite until the
  job is deleted.
- Analysis metadata and validated meeting insights remain in SQLite with the
  transcript until the job is deleted. Raw provider payloads and prompts are
  not persisted.
- Demo mode makes no external API calls. Local Whisper keeps transcript
  processing on the API host after its model is cached.
- Local mode downloads a model from Hugging Face on first use unless the model
  is already cached or `WHISPER_OFFLINE=true`.
- OpenAI, Anthropic, OpenRouter, PackyAPI, and custom live providers receive
  transcript text. A provider key entered in the UI is a one-time request input;
  it is not stored in job state, SQLite, API responses, exports, or URLs.
- Custom provider URLs are checked for private/reserved destinations. Local URL
  access requires the explicit `ALLOW_LOCAL_PROVIDER_URLS=true` opt-in.

This design is suitable for a local/private demonstration. Anyone deploying it
for real client data should define retention, encryption, access control,
backups, audit logging, and deletion requirements.

## Accuracy boundary

Speech recognition can mishear names, accents, technical terms, overlapping
speakers, and noisy recordings. The result requires human review when accuracy
matters.

## Product boundary

The release does not provide:

- speaker diarization
- automatic redaction
- public multi-tenant hosting
- distributed workers
- guaranteed processing speed
- guaranteed transcript accuracy
- reliable YouTube extraction
- external provider delivery guarantees, pricing, rate limits, or retention
