from fastapi import FastAPI, UploadFile
from faster_whisper import WhisperModel

import logging
from constants import ALLOWED_TYPES

# ### Phase 1 — Core transcription (Week 1)
# **Goal:** POST an audio file, get transcript text back synchronously.

# - [ ] FastAPI skeleton with single `POST /transcribe` endpoint
# - [ ] Install faster-whisper, load `small` model at startup
# - [ ] Accept mp3/wav upload, run Whisper, return text in response
# - [ ] Basic input validation (file type, size)
# - [ ] Test with curl: `curl -X POST /transcribe -F "file=@clip.mp3"`


model_size = 'small'

app = FastAPI()
model = WhisperModel(model_size, device='cpu', compute_type="int8")


def transcribe_file(file: UploadFile){
    segments, info = model.transcribe(file, beam_size=5)
    
}


@app.post('/transcribe')
async def transcribe(file: UploadFile): #here we get a file
    file_name = file.filename
    file_size = file.size
    file_headers = file.headers
    content_type = file.content_type # we need this one

    # later agg a link
    if content_type in ALLOWED_TYPES:
        res = transcribe_file(file)
        return {"result": res}
    else:
        raise TypeError(f"{content_type} doesn't supported")
    return {
        "file_name": file_name,
        "file_size": file_size,
        "file_headers": file_headers,
        "file_content_type": content_type,
    }