from fastapi import FastAPI, UploadFile, Request, HTTPException
from faster_whisper import WhisperModel
from user_agents import parse

from datetime import timedelta
from pathlib import Path
import logging
import os
import shutil

from constants import ALLOWED_TYPES, BROWSER_REQUESTS, CLI_REQUESTS
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
async def transcribe(request: Request, file: UploadFile): 

    # 1. define from there the request was send
    user_agent_header = request.headers.get('user-agent')
    user_agent = parse(user_agent_header)

    source_family = user_agent.browser.family
    
    print(f"source: {source_family}")

    # content_type = file.content_type # could be mfaked, need to check magic bytes
    content_type = utils.determine_type(file)

    # later agg a link + divide: for video you need to extract the audio
    if content_type in ALLOWED_TYPES:
        res, info = transcribe_file(file)
        parsed_res_info = parse_res(res, info)

        res = utils.convert_to_uploadfile(parsed_res_info)

        # return {"result": res}
    else:
        raise TypeError(f"{content_type} doesn't supported")


    if source_family in CLI_REQUESTS:
        # if it's here -> it can send only 1) links to sites-media (paths to media  (later))
        #here, a user sends a file. we can handle it as an ordinary file.. or this file go to the uplaodfile ahead?
        pass
    elif source_family in BROWSER_REQUESTS:
        # if it's here -> it should accept a file (for now. later can try to use links)
        pass
    else:
        raise HTTPException(status_code=403, detail='Forbidden')
