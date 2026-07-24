# Privacy and limitations

## Local data behavior

- Uploaded bytes are written to a unique job directory.
- The worker deletes that directory after completion or failure.
- Job metadata, status, errors, and transcript JSON remain in SQLite until the
  job is deleted.
- Demo mode makes no external API calls.
- Local mode downloads a model from Hugging Face on first use unless the model
  is already cached or `WHISPER_OFFLINE=true`.

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
