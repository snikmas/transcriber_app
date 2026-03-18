from unittest.mock import patch
import pytest
import src.jobs as jobs
import src.worker as worker

def test_worker_stop_iteration():
   
    with pytest.raises(StopIteration):
        with patch('src.worker.jobs.cur_queue') as mock_queue1:
            all_jobs = {"job_123": {
                    "is_url": None,
                    "source_family": "ok",
                    "filepath": 'ds',
                    "filename": "name",
                },
                "job_456": {
                    "is_url": None,
                    "source_family": "ok",
                    "filepath": 'ds',
                    "filename": "name",
                }}
            with patch('src.worker.jobs.all_jobs', all_jobs):
                mock_queue1.get.side_effect = ['job_123', 'job_456', StopIteration]
                with patch('src.worker.database.update_job'):
                    worker.worker()
            