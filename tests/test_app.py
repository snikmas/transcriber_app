import time

from fastapi.testclient import TestClient

from main import create_app


def submit_demo_job(client, filename: str = "demo.wav") -> str:
    response = client.post(
        "/transcribe",
        files={"file": (filename, b"repository-owned-demo-bytes", "audio/wav")},
    )
    assert response.status_code == 202
    return response.json()["job_id"]


def wait_for_terminal_job(client, job_id: str) -> dict:
    for _ in range(100):
        job = client.get(f"/transcribe/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Job did not finish")


def test_health_exposes_demo_readiness(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "demo",
        "model": "tiny",
        "model_readiness": "demo-ready",
        "max_upload_mb": 1,
    }


def test_upload_process_result_and_cleanup(client, settings):
    job_id = submit_demo_job(client, "../../unsafe name.wav")
    job = wait_for_terminal_job(client, job_id)

    assert job["status"] == "completed"
    assert job["filename"] == "unsafe name.wav"
    assert job["result"]["engine"] == "deterministic-demo"
    assert job["result"]["word_count"] > 10
    assert not (settings.upload_dir / job_id).exists()


def test_completed_result_survives_repository_read(client):
    job_id = submit_demo_job(client)
    completed = wait_for_terminal_job(client, job_id)

    reread = client.get(f"/transcribe/{job_id}")

    assert reread.status_code == 200
    assert reread.json()["result"] == completed["result"]


def test_list_and_delete_job(client):
    job_id = submit_demo_job(client)
    wait_for_terminal_job(client, job_id)

    jobs = client.get("/jobs").json()
    deleted = client.delete(f"/jobs/{job_id}")

    assert any(job["job_id"] == job_id for job in jobs)
    assert deleted.json() == {"job_id": job_id, "deleted": True}
    assert client.get(f"/transcribe/{job_id}").status_code == 404


def test_active_job_cannot_be_deleted(client, monkeypatch):
    monkeypatch.setattr(
        client.app.state.job_service.job_queue,
        "put",
        lambda _job_id: None,
    )
    job_id = submit_demo_job(client)

    response = client.delete(f"/jobs/{job_id}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "job_active"


def test_missing_job_is_stable_404(client):
    response = client.get("/transcribe/not-a-job")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "job_not_found"


def test_rejects_unsupported_extension(client):
    response = client.post(
        "/transcribe",
        files={"file": ("notes.txt", b"not media", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_format"


def test_rejects_empty_file(client):
    response = client.post(
        "/transcribe",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "empty_file"


def test_rejects_oversized_upload_and_cleans_temp(client, settings):
    response = client.post(
        "/transcribe",
        files={"file": ("large.wav", b"x" * (1024 * 1024 + 1), "audio/wav")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"
    assert list(settings.upload_dir.glob("*")) == []


def test_startup_cleans_abandoned_upload_directories(settings):
    abandoned = settings.upload_dir / "old-job"
    abandoned.mkdir(parents=True)
    (abandoned / "input.wav").write_bytes(b"unfinished")

    with TestClient(create_app(settings)):
        assert not abandoned.exists()
