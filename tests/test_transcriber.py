import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import src.transcriber as transcriber

# 1. transcribe_file()
# - test_transcribe_file_deafult_result
# - test_trasncribe_file_none
# - test_trasncribe_file_wrong_path

def test_transcribe_file_default_result():
    fake_file = MagicMock(spec=Path)
    fake_file.return_value = True

    fake_segment = MagicMock()
    fake_info = MagicMock()

    with patch('src.transcriber.model') as mock_model:
        mock_model.transcribe.return_value = ([fake_segment], fake_info)

        segments, info = transcriber.transcribe_file(fake_file)
    
    assert segments == [fake_segment]
    assert info == fake_info

    fake_file.unlink.assert_called_once()