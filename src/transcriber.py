import logging
from pathlib import Path
from src.parsers import model

def transcribe_file(temp_file: Path) -> tuple[dict, dict]:
    logging.info('transcribe file')
    try: 
        segments, info = model.transcribe(temp_file, vad_filter=True)
        all_segments = list(segments)
        return all_segments, info
    finally:
        if (temp_file.exists()):
            temp_file.unlink()

