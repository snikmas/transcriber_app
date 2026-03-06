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




def transcribe_video_subtitles(video_subtitles: dict):
    json3 = next((s for s in video_subtitles if s['ext'] == 'json3'), None)
    
    logging.info(f'JSON3 {json3.get('url')}')
    url = json3.get('url')
    # saved_path = download_file(url)
    
    return