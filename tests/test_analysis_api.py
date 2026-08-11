import time
from dataclasses import replace

from fastapi.testclient import TestClient

from main import create_app


def _completed_job(client: TestClient) -> str:
    response = client.post("/transcribe", files={"file": ("meeting.wav", b"demo", "audio/wav")})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    for _ in range(100):
        if client.get(f"/transcribe/{job_id}").json()["transcription_status"] == "completed":
            return job_id
        time.sleep(0.01)
    raise AssertionError("transcription did not finish")


def test_analysis_route_is_idempotent_and_never_exposes_internal_fields(client):
    job_id = _completed_job(client)
    first = client.post(f"/transcribe/{job_id}/analysis")
    second = client.post(f"/transcribe/{job_id}/analysis")

    assert first.status_code == second.status_code == 202
    assert first.json()["analysis_id"] == second.json()["analysis_id"]
    body = client.get(f"/transcribe/{job_id}").json()
    assert "input_path" not in body
    assert "api_key" not in body
    assert "prompt" not in body


def test_analysis_failure_is_partial_success_and_retry_keeps_transcript(client):
    job_id = _completed_job(client)

    class FailingEngine:
        def analyze(self, *_args):
            raise RuntimeError("provider response and secret must not leak")

    client.app.state.worker.analysis_engine = FailingEngine()
    assert client.post(f"/transcribe/{job_id}/analysis").status_code == 202
    for _ in range(100):
        job = client.get(f"/transcribe/{job_id}").json()
        if job["analysis_status"] == "failed":
            break
        time.sleep(0.01)
    assert job["status"] == "partial_success"
    assert job["transcription_status"] == "completed"
    assert job["result"] is not None
    assert job["analysis"]["error"] == "Analysis failed."
    assert "secret" not in str(job).lower()

    # A retry queues analysis only; the durable transcript remains intact.
    retry = client.post(f"/transcribe/{job_id}/analysis/retry")
    assert retry.status_code == 202
    assert retry.json()["analysis_id"] == job["analysis"]["analysis_id"]


def test_analysis_missing_job_and_invalid_live_configuration_are_stable(client, settings):
    missing = client.post("/transcribe/not-found/analysis")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "job_not_found"

    # The dataclass is frozen; use a new app setting only to exercise the
    # request-level configuration guard without supplying a credential.
    live_settings = replace(settings, analysis_mode="live", analysis_provider="openai")
    with TestClient(create_app(live_settings)) as live_client:
        job_id = _completed_job(live_client)
        response = live_client.post(f"/transcribe/{job_id}/analysis")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "provider_key_missing"
