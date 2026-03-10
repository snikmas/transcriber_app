from pathlib import Path
import ffmpeg
import logging
import src.parsers as parsers
import os
from dotenv import load_dotenv
import src.utils as utils
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter
from youtube_transcript_api.proxies import GenericProxyConfig
from googleapiclient.discovery import build

load_dotenv()
formatter = JSONFormatter()


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

    ytt_api = YouTubeTranscriptApi(proxy_config=GenericProxyConfig(
        http_url=os.getenv("PROXY"),
        https_url=os.getenv("PROXY"),
    ))

    transcript_list = ytt_api.list(id)
    try: 
        transcript = transcript_list.find_manually_created_transcript(['en'])
    
    except ValueError:
        logging.error(f"[EXTRACTOR] can't get manually transcript. trying to get automatic..")
        transcript = transcript_list.find_transcript(['en'])
    except Exception as e:
        raise Exception(f"[extractor]: {e}")

    try:
        subtitles = transcript.fetch()
        logging.info(f'{type(subtitles)}')
        result_json = parsers.parsed_res(fetched_transcript=subtitles) 
        # fi none... ok, it's none
    except Exception as e:
        raise Exception(f'[Extractor] {e}')


    return result_json
    

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
