import pytest
import src.jobs as jobs
from unittest.mock import  patch
import uuid

@pytest.fixture
def create_job_default_params():
    with patch('src.database.database.add_job'):
        result = jobs.create_job(
            filename='video_1.mp4',
            source_family='ui',
            file_type='mp4'
        ) 
        parsed_uuid = uuid.UUID(str(result))
    yield str(parsed_uuid)
    return str(parsed_uuid)

# @patch('src.database.database.add_job')
@pytest.fixture
def create_job_from_url():
    with patch('src.database.database.add_job'):
        result = jobs.create_job(
            source_family='browser',
            is_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL9tY0BWXOZFvYb2p8nH3UX0DpDVuPEw24&index=6&start_radio=1&t=43s'
        )
        parsed_uuid = uuid.UUID(str(result))
    yield str(parsed_uuid)
    return str(parsed_uuid)


@pytest.fixture
def create_job_from_broken_params():
    with patch('src.database.database.add_job'):
        result = jobs.create_job(
            source_family='aa'
        )
        parsed_uuid = uuid.UUID(str(result))
    yield str(parsed_uuid)
    return str(parsed_uuid)
