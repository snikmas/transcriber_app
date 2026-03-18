import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
with patch('faster_whisper.WhisperModel'):
    import src.parsers as parsers
#functions
# 1) save_file(source)
# - check that it really saves file
# - check what if the file is corrupted - no need - it's always saves everytohng
# - check if there're None

def write_to_file(path: str, content: bytes):
    with open (path, 'wb') as handle:
        handle.write(content)

def test_save_to_file_default():
    path = '/home/snikmas/video_1.mp4'
    fake_content = b'line1\nline1\n'
    m = mock_open()

    with patch('builtins.open', m):
        result = write_to_file(path, fake_content)

    m.assert_called_once_with(path, 'wb') # right arguments?
    m().write.assert_called_once_with(fake_content)
    
        
def test_save_file_none():
    with pytest.raises(AttributeError):
        parsers.save_file(None) #i tihnk i have to pass mock
        
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
    with pytest.raises(TypeError):
        parsers.parse_to_file(None, None)

# 3) parsed_res
# - check if all_gsegments ok 
# - check if tf ther're fetched transcript ok
# - check if everytihng there (but maybe no need to check, there're if elif else statement, nohting wrong
# - check what if there' nohting)
# - check what if the data doesn't exist/ corrupted

def create_segment_mock(start, end, text, duration):
    seg = MagicMock()
    seg.start = start
    seg.end = end
    seg.duration = duration
    seg.text = text
    return seg

def test_parsed_res_default(): # crate a test with broken? idk
    # not good? cuz it checks for types, not for json
    all_segments = []
    all_segments.append(create_segment_mock(12, 23, "this is the best text ever", 123))
    all_segments.append(create_segment_mock(32, 344, "this is the second best text ever", 555))
    
    # or do mock type?
    info = Mock()
    info.duration = 20
    info.language = 'en'
    info.language_probability = 0.32

    res = parsers.parsed_res(all_segments=all_segments, filename="file_name", info=info)
    assert isinstance(res, dict)

def test_parsed_res_only_fetched_transcript():
    fetched_transcript = []
    fetched_transcript.append(create_segment_mock(12, 122, "this is the best text ever", 123))
    fetched_transcript.append(create_segment_mock(124, 134, "this is the second best text ever", 555))
    
    res = parsers.parsed_res(fetched_transcript=fetched_transcript, filename="file_name")

    assert isinstance(res, dict)

def test_parsed_res_none_returns_type_error():
    with pytest.raises(TypeError):
        parsers(None, None, None, None)

def test_parsed_res_if_not_full_data():
    all_segments = []
    all_segments.append(create_segment_mock(12, 32, "this is the best text ever", 123))
    all_segments.append(create_segment_mock(123, 324, "this is the second best text ever", 555))
    
    with pytest.raises(AttributeError):
        parsers.parsed_res(all_segments=all_segments)
    
