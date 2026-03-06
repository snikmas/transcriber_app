from fastapi import UploadFile
from pathlib import Path
from faster_whisper import WhisperModel
import shutil
import logging
import src.utils as utils
import urllib.request
import requests
import json
import io


base_dir = Path(__file__).resolve().parent
temp_dir = base_dir / 'temp_dir'

model_size = 'tiny'

model = WhisperModel(model_size, device='cpu', compute_type="int8")

def save_file(source: UploadFile) -> Path:
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"temp_{source.filename}"

    with open (temp_file_path, 'wb') as buffer:
        shutil.copyfileobj(source.file, buffer)
    
    return temp_file_path


def parse_to_file(full_info: dict):  
    
    temp_file = temp_dir / f"temp_res.txt"
    try:
        with open (temp_file, 'w') as f:
            f.write(f"FILE INFO: \nLanguage: {full_info.get("language")}\nLanguage Probability: {full_info.get("language_probability")}\nDuration: {full_info.get("duration")}\n\nTRANSCRIPTION:\n")
            f.write(full_info.get('transcript'))
        return temp_file
    except FileNotFoundError:
        logging.error("[PARSERS] The file not found error") #actually it's impossible. but what if


def parsed_res(all_segments: list, info: dict, filename: str) -> dict:

    dict_seg_list = [{
            'start_t': utils.formatting_seconds(s.start),
            'end_t': utils.formatting_seconds(s.end),
            'content': s.text,
        } for s in all_segments]
        
    return {
        "filename": filename,
        "duration": utils.formatting_seconds(info.duration),
        "language": info.language.upper(),
        "language Probability": f"{info.language_probability:.1%}",
        "transcript": dict_seg_list
    }
    

# def download_file(url: str) -> Path:

#     # 1. get user_agent
#     try:
#         res = requests.get('https://httpbin.org/headers').json().get('headers')
#         user_agent = res.get('User-Agent')

#         logging.info(f"user_agent: {user_agent}")
#         logging.info(f"response headers: {res}\n\n")
#         logging.info('we are in the downloadin\n\n')
#         my_headers = {
#             "User-Agent": user_agent,
#             "Accept-Language": "en-US,en;q=0.9",
#             "Accept": "application/json",
#             "Referer": "https://www.youtube.com/" #for now
#         }


#         res  = requests.get(url, headers=my_headers, timeout=10)
#         content = res.json()
#         res.raise_for_status()

#         logging.info(f"content: \n{content}\n\n")
#         # we can c all here.. asve file?

#         file_obj = io.BytesIO(json.dumps(content).encode('utf-8'))

#         path = save_file(file_obj)
#         return path

#     except Exception as e:
#         logging.error(f"Error during downloading: {e}")

#     pass


