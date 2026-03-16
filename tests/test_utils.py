import pytest
import src.utils as ut
import pytest_asyncio 
from unittest.mock import AsyncMock

# 1) formatting secconds
def test_formatting_seconds_only_seconds_basic():
    assert ut.formatting_seconds(seconds=213) == '0:03:33'

def test_formatting_seconds_only_seconds_large_amount():
    with pytest.raises(OverflowError) as e:
        ut.formatting_seconds(seconds=999999999999999999)

def test_formatting_seconds_only_seconds_none():
    assert ut.formatting_seconds(seconds=None) == '0:00:00'

def test_formatting_seconds_only_seconds_zero():
    assert ut.formatting_seconds(seconds=0) == '0:00:00'

# ===========

def test_formatting_seconds_only_yt_duration_basic():
    assert ut.formatting_seconds(yt_duration='PT1H23M45S') == '1:23:45'

def test_formatting_seconds_only_yt_none():
    assert ut.formatting_seconds(yt_duration=None) == '0:00:00'
    
def test_formatting_seconds_only_yt_zero():
    assert ut.formatting_seconds(yt_duration='PT0S') == '0:00:00'

def test_formatting_seconds_seconds_and_yt_durations():
    assert ut.formatting_seconds(seconds=2323, yt_duration='PT4S') == '0:38:43'


# 2) determinte type:
# - send not allowed type
# - send allowed
# - send nothign/none
# 3) passing_url
# - pass random url
# - pass with a lot of parameters/queries url
# - pass none/nothing

#2) determine_type
@pytest.mark.asyncio 
async def test_determine_type_defatest_ult_video():
    fake = AsyncMock()
    path = '/home/snikmas/video_1.mp4'
    with open (path, 'rb') as f:
        real_bytes = f.read(2048)

    fake.read.return_value = real_bytes

    assert await ut.determine_type(fake) == 'mp4'

@pytest.mark.asyncio
async def test_determine_type_defatest_ult_audio():
    fake = AsyncMock()
    path = '/home/snikmas/work/english/Cambridge IELTS 11/IELTS11_Test1_Section1.mp3'
    with open (path, 'rb') as f:
        real_bytes = f.read()
    fake.read.return_value = real_bytes

    assert await ut.determine_type(fake) == 'mp3'

@pytest.mark.asyncio  
async def test_determine_type_invalid_value():
    # should return None or error?
    fake = AsyncMock()
    path = '/home/snikmas/Desktop/nanobana-generated-image.jpg'
    with open (path, 'rb') as f:
        real_bytes = f.read(2048)
    fake.read.return_value = real_bytes

    assert await ut.determine_type(fake) == None

@pytest.mark.asyncio
async def test_determine_type_none():
    with pytest.raises(TypeError) as e:
        await ut.determine_type(None)

# 3) passing_url
def test_passing_url_defatest_ult():
    url = 'https://www.youtube.com/watch?v=5MuIMqhT8DM'
    assert ut.parsing_url(url) == '5MuIMqhT8DM'
    
def test_passing_url_many_parameters_and_queries():
    url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL9tY0BWXOZFvYb2p8nH3UX0DpDVuPEw24&index=6&start_radio=1&t=43s'
    assert ut.parsing_url(url) == 'dQw4w9WgXcQ'

def test_passing_url_none():
    with pytest.raises(TypeError):
        ut.parsing_url(None)
        
    