import pytest
import src.jobs as jobs
# from file jobs imporrt functios

# def test_functions
# result = function(a a)
# assert result == what)we want
#run tests :pytests or tests/ or -v or -v -s

#@pytest.fixture for the same code

def test_create_job_using_video():
    uuid_str = jobs.create_job(
        file_path='video_1.mp4',
        filename='video_1.mp4',
        source_family="Browser",
        file_type='mp4',
        is_url=None
    )
    
    assert jobs.all_jobs.get(uuid_str) != None
    
    
