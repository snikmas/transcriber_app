from fastapi import FastAPI, UploadFile
from faster_whisper import WhisperModel

from datetime import timedelta
from pathlib import Path
import logging
import os
import shutil

from constants import ALLOWED_TYPES
import utils

os.environ["HF_HUB_OFFLINE"] = "1"
logging.basicConfig(level=logging.INFO)

# ### Phase 1 — Core transcription (Week 1)
# **Goal:** POST an audio file, get transcript text back synchronously.

# - [X] FastAPI skeleton with single `POST /transcribe` endpoint
# - [X] Install faster-whisper, load `small` model at startup -< change for tiny for now
# - [X] Accept mp3/wav upload, run Whisper, return text in response
# - [ ] Basic input validation (file type, size)
# - [ ] Test with curl: `curl -X POST /transcribe -F "file=@clip.mp3"`


model_size = 'tiny'

app = FastAPI()
model = WhisperModel(model_size, device='cpu', compute_type="int8")

base_dir = Path(__file__).resolve().parent
temp_dir = base_dir / 'temp_dir'

def transcribe_file(file: UploadFile):

    # 2 options:
    # 1. save the file and read it
    # 2. read its bytes. requires more RAM, faster
    temp_file = temp_dir / f"temp_{file.filename}"
    
    with open (temp_file, 'wb') as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try: 
        segments, info = model.transcribe(temp_file, vad_filter=True)
        all_segments = list(segments)
        return all_segments, info
    finally:
            if (temp_file.exists()):
                temp_file.unlink()


def parse_res(all_segments: dict, info: dict):  
    
    temp_file = temp_dir / f"temp_res.txt"

    with open (temp_file, 'w') as f:
        f.write(f"FILE INFO: \nLanguage: {info.language.upper()}\nLanguage Probability: {info.language_probability:.1%}\nDuration: {utils.formatting_seconds(info.duration)}\n\nTRANSCRIPTION:\n")

        for s in all_segments:
            start_t = utils.formatting_seconds(s.start)
            end_t = utils.formatting_seconds(s.end)
            f.write(f'[{start_t} -> {end_t}]: {s.text}\n')


        f.write('\n')
    return temp_file




@app.post('/transcribe')
async def transcribe(file: UploadFile): #here we get a file
    # file_size = file.size
    content_type = file.content_type # we need this one

    # later agg a link
    if content_type in ALLOWED_TYPES:
        res, info = transcribe_file(file)
        parsed_res = parse_res(res, info)
        # how to output it?

        return {"result": parsed_res}
    else:
        raise TypeError(f"{content_type} doesn't supported")

