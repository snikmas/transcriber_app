from unittest.mock import patch, AsyncMock
with patch('faster_whisper.WhisperModel'):
    from fastapi.testclient import TestClient
    from main import app
import logging


client = TestClient(app)

def test_app_get_jobs():
    res = client.get('/jobs')
    logging.info(res)
    logging.info(res.json())
    assert res.status_code == 200

def test_app_get_job(create_job_default_params):
    res = client.get(f'/transcribe/{create_job_default_params}')
    assert res.status_code == 200
    

def test_app_post_job(create_job_default_params):
    res = client.get(f'/transcribe/{create_job_default_params}')
    assert res.status_code == 200

def test_app_delete_job(create_job_default_params):
    with patch('src.database.database.delete_job'):
        res = client.delete(f'/jobs/{create_job_default_params}')
    assert res.status_code == 200

def test_app_post():
    with patch('main.utils.determine_type', new_callable=AsyncMock, return_value='mp3'):
        with patch('main.parsers.save_file'):
            with patch('src.database.database.add_job'):
                res = client.post('/transcribe', files={'file': ('test.mp3', b'fake audio bytes', 'audio/mpeg')}, headers={'x-source': 'curl'})
    assert res.status_code == 201