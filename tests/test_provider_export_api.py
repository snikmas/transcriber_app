import time
import wave
from dataclasses import replace
from pathlib import Path

import main
from src.analysis.providers import ProviderResponse
from src.analysis.statuses import ProviderProtocol


def test_demo_audio_fixture_has_reproducible_demo_length():
    fixture = Path(__file__).parents[1] / "samples" / "northstar-demo-60s.wav"
    with wave.open(str(fixture), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    assert 60 <= duration <= 90


def _completed_job(client) -> str:
    response = client.post("/transcribe", files={"file": ("meeting.wav", b"demo", "audio/wav")})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    for _ in range(100):
        job = client.get(f"/jobs/{job_id}").json()
        if job["transcription_status"] == "completed":
            return job_id
        time.sleep(0.01)
    raise AssertionError("transcription did not finish")


def test_demo_provider_connection_test_is_redacted_and_categorized(client):
    response = client.post(
        "/providers/test",
        json={"provider": "demo", "model": "deterministic-meeting-v1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == body["category"] == "ok"
    assert "secret" not in response.text
    assert "prompt" not in response.text.lower()


def test_provider_test_rejects_missing_live_key(client):
    response = client.post("/providers/test", json={"provider": "openai", "model": "gpt"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "provider_key_missing"


def test_client_supplied_key_is_ignored_and_never_echoed(client):
    secret = "client-keys-are-not-accepted"

    response = client.post(
        "/providers/test",
        json={"provider": "openai", "model": "gpt", "api_key": secret},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "provider_key_missing"
    assert secret not in response.text


def test_selected_provider_uses_server_environment_key_when_ui_key_is_blank(client, monkeypatch):
    secret = "server-side-deepseek-key"
    captured = {}

    class FakeDeepSeekProvider:
        provider_id = "deepseek"
        protocol = ProviderProtocol.OPENAI_CHAT

        def generate(self, messages, *, model, timeout):
            del messages, timeout
            return ProviderResponse(
                structured={
                    "summary": "Environment key accepted.",
                    "decisions": [],
                    "action_items": [],
                    "open_questions": [],
                    "follow_ups": [],
                },
                actual_model=model,
            )

    def fake_provider_from_config(provider, *, api_key, **kwargs):
        del kwargs
        captured.update(provider=provider, api_key=api_key)
        return FakeDeepSeekProvider()

    client.app.state.settings = replace(
        client.app.state.settings,
        analysis_mode="demo",
        deepseek_api_key=secret,
    )
    monkeypatch.setattr(main, "provider_from_config", fake_provider_from_config)
    job_id = _completed_job(client)

    response = client.post(
        f"/jobs/{job_id}/analysis",
        json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )

    assert response.status_code == 202
    assert captured == {"provider": "deepseek", "api_key": secret}
    assert secret not in response.text


def test_job_export_allowlist_covers_all_server_formats(client):
    job_id = _completed_job(client)
    expected = {
        "combined_json": "application/json",
        "meeting_notes_markdown": "text/markdown",
        "transcript_json": "application/json",
        "transcript_markdown": "text/markdown",
        "transcript_txt": "text/plain",
        "transcript_srt": "application/x-subrip",
    }

    for format_name, media_type in expected.items():
        response = client.get(f"/jobs/{job_id}/export", params={"format": format_name})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(media_type)
        assert "input_path" not in response.text
        assert "api_key" not in response.text
        assert "prompt" not in response.text

    invalid = client.get(f"/jobs/{job_id}/export", params={"format": "html"})
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "unsupported_export_format"
