from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import create_app
from src.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        mode="demo",
        database_path=tmp_path / "jobs.sqlite3",
        upload_dir=tmp_path / "uploads",
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        offline=False,
        max_upload_mb=1,
        poll_interval_seconds=0.01,
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
