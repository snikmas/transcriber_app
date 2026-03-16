import pytest
import src.jobs as jobs
import pytest_asyncio 
from unittest.mock import AsyncMock
import uuid
import src.constants as const

# fixtures
@pytest.fixture
def create_job_default_params():
    result = jobs.create_job(
        filename='video_1.mp4',
        source_family='ui',
        file_type='mp4'
    ) 
    parsed_uuid = uuid.UUID(str(result))
    return str(parsed_uuid)

@pytest.fixture
def create_job_from_url():
    result = jobs.create_job(
        source_family='browser',
        is_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL9tY0BWXOZFvYb2p8nH3UX0DpDVuPEw24&index=6&start_radio=1&t=43s'
    )
    parsed_uuid = uuid.UUID(str(result))
    return str(parsed_uuid)


@pytest.fixture
def create_job_from_broken_params():
    result = jobs.create_job(
        source_family='aa'
    )
    parsed_uuid = uuid.UUID(str(result))
    return str(parsed_uuid)


# 1) create_job
# - pass nothing/none
# - pass common arugments / part of them

def test_create_job_default_path_returns_valid_uuid(create_job_default_params):    
    assert isinstance(create_job_default_params, str) # why false?

def test_create_job_default_url_returns_valid_uuid(create_job_from_url):
    assert isinstance(create_job_from_url, str)

# does it really should work lik ethat?
def test_create_job_broken_parameters_still_returns_valid_uuid(create_job_from_broken_params):
    assert isinstance(create_job_from_broken_params, str)


# 2) get_job
# - pass nothing/none
# - pass invalid job_id; valid; pass not str
def test_get_job_returns_valid_job(create_job_default_params):
    uuid_str = create_job_default_params # what to do? this fixture would actually run it but where to put this value? save in the params?
    job = jobs.get_job(uuid_str) # should we check its type or that its int eh dcit？

    #idk check it or from the jobs
    assert job == {'job_id': uuid_str, **jobs.all_jobs.get(uuid_str)}

def test_get_job_returns_error(create_job_default_params):
    with pytest.raises(Exception) as e:
        jobs.get_job('random_str')

def test_get_job_returns_error_for_none(create_job_default_params):
    with pytest.raises(Exception) as e:
        jobs.get_job(None)

# 3) delete_job
# - pass invalid arguments
# - pass nothing/none
# - check deletion
def test_delete_job_deletes_it(create_job_default_params):
    jobs_before = len(jobs.all_jobs)
    jobs.delete_job(create_job_default_params)
    assert len(jobs.all_jobs) == jobs_before - 1

def test_delete_job_handles_invalid_args(create_job_default_params):
    with pytest.raises(KeyError):
        jobs.delete_job('aa')

def test_delete_job_handles_none():
    with pytest.raises(KeyError):
        jobs.delete_job(None)
        
# 4) get_result
# - pass invalid arguments
# - pass nothing/none
# - check result
def test_get_result_returns_job_result(create_job_default_params):

    res = jobs.get_result(create_job_default_params)
    assert res == jobs.all_jobs.get(create_job_default_params)['result']

def test_get_result_invalid_args_raises_keyerror():
    with pytest.raises(KeyError):
        jobs.get_result('aa')

def test_get_result_none_raises_keyerror():
    with pytest.raises(KeyError):
        jobs.delete_job(None)

# 5) update_status:
# - pass invalid arguments
# - pass nothing/none
# - check updates
def test_update_status_result(create_job_default_params):
    jobs.update_status(create_job_default_params, const.Job_Status.PROCESSING)
    job = jobs.all_jobs.get(create_job_default_params)
    assert job['status'] == const.Job_Status.PROCESSING.value