from pathlib import Path
import ffmpeg
import logging
import src.parsers as parsers
import os
from dotenv import load_dotenv
import src.utils as utils
from googleapiclient.discovery import build
import yt_dlp
import json
import tempfile

load_dotenv()


def extract_audio(temp_file: Path) -> Path:
    output_path = temp_file.with_suffix('.wav')
    try:
        #if we handle only one file for time, its okay. but later if 2+ files -> problems
        ffmpeg.input(str(temp_file)).output(str(output_path), acodec='pcm_s16le', ar=16000, ac=1).run(overwrite_output=True, quiet=True)
        return output_path
    except ffmpeg.Error as e:
        logging.error("[EXTRACTOR] ffmpeg error: %s", e.stderr.decode())    
        raise e
    

def get_subtitles(id: str) -> dict:
    url = f'https://www.youtube.com/watch?v={id}'

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'subtitlesformat': 'json3',
            'skip_download': True,
            'proxy': os.getenv('PROXY'),
            'outtmpl': f'{tmpdir}/%(id)s',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        json_files = list(Path(tmpdir).glob('*.json3'))
        if not json_files:
            raise Exception(f'[extractor] No subtitles found for {id}')

        with open(json_files[0]) as f:
            subtitle_data = json.load(f)

    transcript = []
    for event in subtitle_data.get('events', []):
        if 'segs' not in event:
            continue
        start_ms = event.get('tStartMs', 0)
        duration_ms = event.get('dDurationMs', 0)
        text = ''.join(seg.get('utf8', '') for seg in event['segs']).strip()
        if not text:
            continue
        transcript.append({
            'start_t': utils.formatting_seconds(start_ms / 1000),
            'end_t': utils.formatting_seconds((start_ms + duration_ms) / 1000),
            'content': text,
        })

    logging.info(f'[extractor] got {len(transcript)} subtitle entries')
    return {"transcript": transcript}
    

def get_video_info(id: str) -> dict:

    logging.info("in the get vide info")

    http = utils.get_http()

    youtube = build('youtube', 'v3', developerKey=os.getenv('GOOGLE_API_KEY'), http=http)

    response = youtube.videos().list(
        part='snippet,contentDetails',
        id=id
    ).execute()

    items = response.get('items', [])
    if not items: 
        logging.info("not items??\n\n")
        return {}
    
    snippet = items[0]['snippet']
    content_details = items[0]['contentDetails']
    return {
        "title": snippet.get('title'),
        'description': snippet.get('description'),
        'duration': utils.formatting_seconds(yt_duration=content_details.get('duration')),
        'language': snippet.get('defaultAudioLanguage') or snippet.get('defaultLanguage'),
        'channel': snippet.get('channelTitle')
    }
