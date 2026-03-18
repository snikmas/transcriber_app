import pytest
import src.jobs as jobs
from unittest.mock import AsyncMock, patch
import src.constants as const

# fixtures
# @patch('src.database.database.add_job')


# 1) create_job
def test_create_job_default_path_returns_valid_uuid(create_job_default_params):    
    assert isinstance(create_job_default_params, str) # why false?

def test_create_job_default_url_returns_valid_uuid(create_job_from_url):
    assert isinstance(create_job_from_url, str)

# does it really should work lik ethat?
def test_create_job_broken_parameters_still_returns_valid_uuid(create_job_from_broken_params):
    assert isinstance(create_job_from_broken_params, str)


# 2) get_job
def test_get_job_returns_valid_job(create_job_default_params):
    uuid_str = create_job_default_params 
    job = jobs.get_job(uuid_str) 

    assert job == {'job_id': uuid_str, **jobs.all_jobs.get(uuid_str)}

def test_get_job_returns_error():
    with pytest.raises(Exception) as e:
        jobs.get_job('random_str')

def test_get_job_returns_error_for_none():
    with pytest.raises(Exception) as e:
        jobs.get_job(None)

# 3) delete_job
def test_delete_job_deletes_it(create_job_default_params):
    jobs_before = len(jobs.all_jobs)
    with patch('src.database.database.delete_job'):
        jobs.delete_job(create_job_default_params)
    assert len(jobs.all_jobs) == jobs_before - 1

def test_delete_job_handles_invalid_args():
    with patch('src.database.database.delete_job'):
        with pytest.raises(KeyError):
            jobs.delete_job('aa')

def test_delete_job_handles_none():
    with patch('src.database.database.delete_job'):
        with pytest.raises(KeyError):
            jobs.delete_job(None)
        
# 4) get_result
def test_get_result_returns_job_result(create_job_default_params):

    res = jobs.get_result(create_job_default_params)
    assert res == jobs.all_jobs.get(create_job_default_params)['result']

def test_get_result_invalid_args_raises_keyerror():
    with pytest.raises(KeyError):
        jobs.get_result('aa')

def test_get_result_none_raises_keyerror():
    with pytest.raises(KeyError):
        jobs.get_result(None)

# 5) update_status:
def test_update_status_result(create_job_default_params):
    with patch('src.database.database.update_job'):
        jobs.update_status(create_job_default_params, const.Job_Status.PROCESSING)
        job = jobs.all_jobs.get(create_job_default_params)
    assert job['status'] == const.Job_Status.PROCESSING.value