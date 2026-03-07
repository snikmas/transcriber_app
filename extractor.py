from pathlib import Path
import ffmpeg
import logging
import yt_dlp
from src.jobs import all_jobs
import logging
import src.parsers as parsers
import os
from dotenv import load_dotenv
import src.transcriber as transcriber
import httplib2
import socks
import urllib
import src.utils as utils
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter
from youtube_transcript_api.proxies import GenericProxyConfig
from googleapiclient.discovery import build

load_dotenv()
formatter = JSONFormatter()


def extract_audio(temp_file: Path) -> Path:
    output_path = temp_file.with_suffix('wav')
    try:
        #if we handle only one file for time, its okay. but later if 2+ files -> problems
        ffmpeg.input(str(temp_file)).output(str(output_path), acodec='pcm_s16le', ar=16000, ac=1).run(overwrite_output=True, quiet=Tru)
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
    transcript = transcript_list.find_manually_created_transcript(['en'])

    #if its not null: we can get video_id; language; language code; is generated; is translabe; translation languages
    #fetch it
    if transcript is not None:
        subtitles = transcript.fetch()
        logging.info(f'{type(subtitles)}')
        result_json = parsers.parsed_res(fetched_transcript=subtitles)


    return result_json
    # path_to_file = parsers.parse_to_file(json_info=json_formatted) # NOT HERE
    

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
