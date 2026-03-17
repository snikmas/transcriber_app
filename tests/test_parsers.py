import pytest
import src.parsers as parsers
from unittest.mock import Mock
from pathlib import Path
#functions
# 1) save_file(source)
# - check that it really saves file
# - check what if the file is corrupted - no need - it's always saves everytohng
# - check if there're None
def test_save_file_default():
    fake = Mock()
    path = '/home/snikmas/video_1.mp4'
    with open(path, 'rb') as f:
        real_bytes = f.read()

    fake.return_value = real_bytes
    fake.filename = 'name'

    temp_file_path = parsers.temp_dir / f'temp_{fake.filename}'

    assert parsers.save_file(fake) == temp_file_path

def test_save_file_none():
    with pytest.raises(AttributeError):
        parsers.save_file(None)
        
# 2) prase_to_file()
# - check that it works for full_info / json_info
# - check what if there're nothing
# - chech if there're both of them
def test_parse_to_file_full_info():
    full_info = {"info_1": "sometinhg"}
    path_res = parsers.parse_to_file(full_info)
    assert isinstance(path_res, Path)

def test_parse_to_file_json_info():
    json_info = '{"info_1": "sometinhg"}'
    path_res = parsers.parse_to_file(json_info=json_info)
    assert isinstance(path_res, Path)

def test_parse_to_file_none():
    with pytest.raises(FileNotFoundError):
        parsers.parse_to_file()

# 3) parsed_res
# - check if all_gsegments
# - check if tf ther're fetched transcript
# - check if everytihng there (but maybe no need to check, there're if elif else statement, nohting wrong
# - check what if there' nohting)
# - check what if the data doesn't exist/ corrupted
def test_parsed_res_default():
    all_segments = [
        {
            'start': 14,
            'end': 16,
            'text': 'text_one',
            'start': 16,
            'end': 134,
            'text': 'text_two',
         }
    ]
    info = {
        'language': 'en',
        'language_probability': 'wow' #idk how to do that 
    }
    res = parsers.parsed_res(all_segments=all_segments, filename="file_name", info=info)
    assert isinstance(res, dict)