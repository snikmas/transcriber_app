from datetime import timedelta, datetime
from pathlib import Path
from fastapi import UploadFile
import magic
from src.constants import ALLOWED_AUDIO_TYPES, ALLOWED_VIDEO_TYPES
from urllib.parse import urlparse, parse_qs
import logging
import os
from dotenv import load_dotenv
import httplib2
import isodate


load_dotenv()

def formatting_seconds(seconds: int | None = None, yt_duration: str | None = None) -> str:
    if yt_duration is None and seconds == 0: return str(timedelta(0))
    if seconds is not None:   
      return str(timedelta(seconds=int(round(seconds))))
    else:                                                                                 
      return str(timedelta(seconds=int(isodate.parse_duration(yt_duration).total_seconds())))      
     

async def determine_type(file: UploadFile) -> str:
    buffer = await file.read(2048)
    await file.seek(0)
    mime_type =  magic.from_buffer(buffer, mime=True)
    if mime_type in ALLOWED_VIDEO_TYPES: return ALLOWED_VIDEO_TYPES.get(mime_type)
    elif mime_type in ALLOWED_AUDIO_TYPES: return ALLOWED_AUDIO_TYPES.get(mime_type)
    else: return None



def parsing_url(url: str) -> str:
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    video_id = params.get('v', [None])[0]

    return video_id
    

def parse_proxy(proxy: str):
    parsed_proxy = urlparse(proxy)
    logging.info(parsed_proxy)
    return parsed_proxy.scheme, parsed_proxy.hostname, parsed_proxy.port  

def get_http():
    parsed_proxy = urlparse(os.getenv('PROXY'))
    scheme, host, port = parsed_proxy.scheme, parsed_proxy.hostname, parsed_proxy.port
    if scheme == 'socks5':
        proxy_type = httplib2.socks.PROXY_TYPE_SOCKS5
    else: proxy_type = httplib2.socks.PROXY_TYPE_HTTP

    return httplib2.Http(proxy_info=httplib2.ProxyInfo(proxy_type=proxy_type, proxy_host=host, proxy_port=port))
