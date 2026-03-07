from datetime import timedelta
from pathlib import Path
from fastapi import UploadFile
import magic
from src.constants import ALLOWED_AUDIO_TYPES, ALLOWED_VIDEO_TYPES
from urllib.parse import urlparse
import logging
import os
from dotenv import load_dotenv
import socks
import httplib2

load_dotenv()

def formatting_seconds(seconds: int) -> str:
    # timedelta takes seconds as an argument
    total_seconds = int(round(seconds))
    clean_time = timedelta(seconds=total_seconds)
    return str(clean_time)

def convert_to_uploadfile(parsed_res_info: Path) -> UploadFile:
    with open (parsed_res_info, 'rb'):
        upload_file = UploadFile(
            file = parsed_res_info,
            filename=parsed_res_info.name,
            size=parsed_res_info.stat().st_size
            )
        
    return upload_file


async def determine_type(file: UploadFile) -> str:
    print(logging.root.handlers)
    print(logging.root)

    buffer = await file.read(2048)
    await file.seek(0)
    mime_type =  magic.from_buffer(buffer, mime=True)
    if mime_type in ALLOWED_VIDEO_TYPES: return ALLOWED_VIDEO_TYPES.get(mime_type)
    elif mime_type in ALLOWED_AUDIO_TYPES: return ALLOWED_AUDIO_TYPES.get(mime_type)
    else: return None



def pasring_url(url: str):
    parsed_url = urlparse(url)
    logging.info(f'parsed url: {parsed_url}')
    logging.info(f"query: {parsed_url.query[2:]}")

    return parsed_url.query[2:] #not sure is this the best option
    

def parse_proxy(proxy: str):
    parsed_proxy = urlparse(proxy)
    logging.info(parsed_proxy)
    return parsed_proxy.scheme, parsed_proxy.hostname, parsed_proxy.port  #scheme - host - port

def get_http():
    parsed_proxy = urlparse(os.getenv('PROXY'))
    scheme, host, port = parsed_proxy.scheme, parsed_proxy.hostname, parsed_proxy.port
    if scheme == 'socks5':
        proxy_type = httplib2.socks.PROXY_TYPE_SOCKS5
    else: proxy_type = httplib2.socks.PROXY_TYPE_HTTP
    
    return httplib2.Http(proxy_info=httplib2.ProxyInfo(proxy_type=proxy_type, proxy_host=host, proxy_port=port))