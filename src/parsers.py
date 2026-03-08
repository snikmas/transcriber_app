from fastapi import UploadFile
from pathlib import Path
from faster_whisper import WhisperModel
import shutil
import logging
import src.utils as utils
import json


base_dir = Path(__file__).resolve().parent
temp_dir = base_dir / 'temp_dir'
temp_dir.mkdir(exist_ok=True)
temp_file = temp_dir / f'temp_res.json'

model_size = 'tiny'

model = WhisperModel(model_size, device='cpu', compute_type="int8")

def save_file(source: UploadFile) -> Path:
    temp_file_path = temp_dir / f"temp_{source.filename}"

    with open (temp_file_path, 'wb') as buffer:
        shutil.copyfileobj(source.file, buffer)
    
    return temp_file_path


def parse_to_file(full_info: dict | None = None, json_info: str | None = None) -> Path:  

    logging.info(f"temp_file: {temp_file}")
    try:
        with open (temp_file, 'w') as fp:
            if full_info is not None:
                json.dump(full_info, fp, indent=4)
            else: 
                fp.write(json_info)
            logging.info("saved")
        return temp_file
    except FileNotFoundError as e:
        logging.error(f"[PARSERS] The file not found: {e} ") #actually it's impossible. but what if


def parsed_res(all_segments: list | None = None, info: dict | None = None, filename: str | None = None, fetched_transcript: list | None = None) -> dict:

    if all_segments is not None:
        dict_res_list = [{
                'start_t': utils.formatting_seconds(s.start),
                'end_t':   utils.formatting_seconds(s.end),
                'content': s.text,
            } for s in all_segments
        ]

        return {
            "filename": filename,
            "duration": utils.formatting_seconds(info.duration),
            "language": info.language.upper(),
            "language Probability": f"{info.language_probability:.1%}",
            "transcript": dict_res_list
        }
    elif all_segments is None and fetched_transcript:
        dict_res_list = [{
                'start_t': utils.formatting_seconds(s.start),
                'end_t':   utils.formatting_seconds(s.start + s.duration),
                'content': s.text 
            } for s in fetched_transcript
        ]

        return {
            "transcript": dict_res_list
        }

    else:
        raise Exception(f'[parsers] No information to parse: {Exception}')

        
        