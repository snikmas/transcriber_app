from pathlib import Path
import ffmpeg
import logging
import yt_dlp
from src.jobs import all_jobs
import logging
from src.parsers import temp_dir
import os
from dotenv import load_dotenv

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter
from youtube_transcript_api.proxies import GenericProxyConfig

load_dotenv()

PROXY = os.getenv('PROXY')
def extract_audio(temp_file: Path) -> Path:
    output_path = temp_file.with_suffix('wav')
    try:
        #if we handle only one file for time, its okay. but later if 2+ files -> problems
        ffmpeg.input(str(temp_file)).output(str(output_path), acodec='pcm_s16le', ar=16000, ac=1).run(overwrite_output=True, quiet=Tru)
        return output_path
    except ffmpeg.Error as e:
        logging.error("[EXTRACTOR] ffmpeg error: %s", e.stderr.decode())    
        raise e
    

def get_subtitles(id: str):    
    ytt_api = YouTubeTranscriptApi(proxy_config=GenericProxyConfig(
        http_url=os.getenv("PROXY"),
        https_url=os.getenv("PROXY"),
    ))
    transcript_list = ytt_api.list(id)
    transcript = transcript_list.find_manually_created_transcript(['en',])
    logging.info(f"in the get subtitles.. {transcript_list}")

    #if its not null: we can get video_id; language; language code; is generated; is translabe; translation languages
    #fetch it
    if transcript is not None:
        subtitles = transcript.fetch()

    # we can put to another utils etc this formatter
    formatter = JSONFormatter()
    json_formatted = formatter.format_transcript(subtitles, indent=2)

    with open('new_file.json', 'w', encoding='utf-8') as json_file:
        json_file.write(json_formatted)


    



# # yt doesnt work. cuz if autorization
# def video_url_response(video_url: str) -> dict:

#     logging.info(f"getting video info... {video_url}")

#     try:
#         with yt_dlp.YoutubeDL({
#                 'proxy': PROXY,
#                 'ignore_no_formats_error': True,
#                 'skip_download': True,
#                 'writesubtitles': True,
#                 'outtmpl': str('..' / temp_dir / '%(id)s.%(ext)s')
#                 }) as ydl:
#             info = ydl.extract_info(video_url, download=True)
#             logging.info("")

#             logging.info(f"IN THE VIDEO_URL_RESPONSE; INFO: \n")
#             for key in info.keys():
#                 logging.info(f"{key}: {info.get(key)}")
#             return {
#                 'id':           info.get('id'),
#                 'title':        info.get('title'),
#                 'fulltitle':    info.get('fulltitle'),
#                 'duration_str': info.get('duration_string'),
#                 'language':     info.get('en'),
#                 'subtitles':    info.get('subtitles', {}).get('en'), #why none?
#                 'webpage_urli': info['webpage_url'],
#             }

#     except yt_dlp.utils.ExtractorError as e:
#         logging.error(f"Extractor error: {e}")
#         raise e
#     except yt_dlp.utils.DownloadError as e:
#         logging.error(f"Download Error: {e}")
#         raise e
#     pass