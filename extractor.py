from pathlib import Path
import ffmpeg
import logging
import yt_dlp
from src.jobs import all_jobs
import logging

import os
from dotenv import load_dotenv

load_dotenv()

PROXY = os.getenv('PROXY')
def extract_audio(temp_file: Path) -> Path:
    output_path = temp_file.with_suffix('wav') #idk how to handle it?
    try:
        #if we handle only one file for time, its okay. but later if 2+ files -> problems
        ffmpeg.input(str(temp_file)).output(str(output_path), acodec='pcm_s16le', ar=16000, ac=1).run(overwrite_output=True, quiet=Tru)
        return output_path
    except ffmpeg.Error as e:
        logging.error("[EXTRACTOR] ffmpeg error: %s", e.stderr.decode())    
        raise e
    

def get_video_info(video_url: str) -> dict:
    logging.info("getting video info...")

    try:
        with yt_dlp.YoutubeDL({
                'quiet': True,
                'proxy': PROXY,
                'cookiefile': os.getenv("PATH_TO_COOKIES"),
                'ignore_no_formats_error': True,
                }) as ydl:
            info = ydl.extract_info(video_url, download=False)

            return {
                'title':        info.get('title'),
                'fulltitle':    info.get('fulltitle'),
                'duration_str': info.get('duration_string'),
                'language':     info.get('en'),
                'subtitles':    info.get('subtitles', {}).get('en'),
                'webpage_urli': info['webpage_url'],
            }

    except yt_dlp.utils.ExtractorError as e:
        logging.error(f"Extractor error: {e}")
        raise e
    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download Error: {e}")
        raise e
    pass