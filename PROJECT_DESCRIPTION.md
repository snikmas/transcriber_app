# Meeting and Call Processing System: Current Release and Target Description

## What is implemented in this checkout

The portfolio release already implements the first two stages of the workflow:

```text
upload audio/video -> durable transcription job -> schema-validated meeting analysis
-> history/review -> transcript or combined exports
```

The no-key Demo path is deterministic and offline-safe. Local mode uses lazy
`faster-whisper` inference. Analysis supports a deterministic Demo adapter,
OpenAI Responses, Anthropic Messages, OpenRouter, PackyAPI through an
account-supplied OpenAI-compatible base URL, and custom OpenAI/Anthropic
compatible endpoints. Provider keys are request-scoped or environment-backed,
never persisted. The current UI includes provider/model/language controls,
history, retry, deletion, partial-success messaging, meeting notes, and
combined JSON/Meeting Notes Markdown plus transcript JSON/Markdown/TXT downloads.

The release is intentionally a local/small-team product: one in-process worker,
SQLite persistence, no authentication, no diarization, no real-time capture,
and no hosted multi-tenant guarantees. The sections below describe the target
product direction; unchecked items are not claims about current functionality.

## Purpose and next product direction

Keep the existing transcription service as the reliable first stage and evolve
it into a contained meeting and call processing product. The current release
preserves upload validation, the background worker, faster-whisper integration,
timestamped transcript, SQLite job state, restart recovery, cleanup, exports,
Docker setup, and offline tests. Future work should build on those seams rather
than imply that hosted collaboration features already exist.

The product should turn recordings into information that a team can act on:
summaries, decisions, action items, questions, deadlines, and follow-up work.

## Target User Flow

```text
upload audio or video -> background transcription -> persist transcript
-> structured AI analysis -> review business insights -> export
```

The main screen should clearly separate:

- summary;
- decisions;
- action items;
- open questions and follow-ups;
- timestamped transcript.

## Main Product Requirements

The following is the retained product target/roadmap. Items described as
implemented in the opening section are delivered in this checkout; items not
mentioned there remain future work.

### Structured meeting analysis

- Add a provider-neutral analysis stage after successful transcription.
- Validate every analysis result with Pydantic schemas.
- Represent action items as objects with a description, optional owner,
  optional deadline, and explicit unknown handling.
- Represent decisions, questions, and follow-up items as structured lists.
- Persist analysis results separately from the authoritative transcript.
- Show analysis failure without losing a successfully completed transcript.
- Keep a deterministic no-key analysis mode for tests and demonstrations.

### Analysis profiles

The shared architecture should allow different analysis profiles without
duplicating the full processing pipeline.

- Meeting mode is the first required profile: summary, decisions, action items,
  owners when identifiable, deadlines, and unresolved questions.
- Sales/customer-call mode is a later extension: customer needs, objections,
  requested features, and follow-up actions.
- Interview mode is a later extension: discussed topics, candidate claims,
  notable answers, and follow-up questions.

The first release should finish Meeting mode before expanding the number of
profiles.

### Job lifecycle and recovery

- Keep transcription asynchronous and preserve durable queued, processing,
  completed, and failed behavior.
- Extend the job/result model so transcription and analysis states are clear.
- Make retries bounded and safe, and avoid repeating completed transcription
  unnecessarily when only analysis fails.
- Keep source-media cleanup and restart recovery predictable.
- Preserve understandable, client-safe errors for upload, ffmpeg, model,
  provider, schema, and worker failures.

### History and result access

- Add a user-facing history view based on the existing jobs API.
- Show title or safe filename, creation date, duration, status, language, and
  analysis profile.
- Let a user reopen a completed transcript and its analysis.
- Keep deletion rules safe for active jobs and their temporary files.

### Export

- Preserve TXT, JSON, and Markdown transcript exports.
- Add combined Markdown and JSON exports containing both transcript and
  structured business insights.
- Keep structured fields machine-readable so a future client can integrate
  them with a CRM, task tracker, webhook, or internal API.

### Frontend

- Present the workflow as a business tool, not a developer upload test page.
- Show progress separately for transcription and analysis when appropriate.
- Render decisions and action items as scannable cards or lists.
- Keep transcript timestamps available for verification.
- Add clear empty, loading, completed, partial-success, and failed states.
- Preserve the local/private-processing explanation and honest review warning.

### Evaluation and testing

- Use fictional repository-owned recordings and expected structured results.
- Test valid analysis, malformed model output, missing fields, provider errors,
  partial success, persistence, restart recovery, export, and history.
- Keep the fast test suite offline and independent of model downloads.
- Retain a bounded optional real-inference smoke test.

## Client-Facing Presentation

- Lead with the business result: a recording becomes meeting notes and actions.
- Show one complete fictional meeting from upload through insights and export.
- Update screenshots to include summary, decisions, action items, and transcript.
- Record a short local or Docker demonstration.
- Publish the improved client-facing README that currently exists only in the
  local working tree.
- Separate implemented features from possible client adaptations such as CRM
  integration, private deployment, retention policies, or distributed workers.

## Scope Boundaries

Do not turn the project into a Zoom, Otter, or Fireflies competitor. The first
release does not require live conferencing, a calendar bot, real-time capture,
native desktop applications, complicated organizations, or speaker diarization.
Diarization should be added only if it can be made reliable without consuming
disproportionate development time.

## Definition of Ready

The project is ready to present when a new user can process a fictional meeting,
see a durable transcript and schema-validated meeting insights, understand any
partial failure, reopen the result from history, and download a useful combined
export without technical assistance.
