import logging
from fastapi import FastAPI, UploadFile
# ### Phase 1 — Core transcription (Week 1)
# **Goal:** POST an audio file, get transcript text back synchronously.

# - [ ] FastAPI skeleton with single `POST /transcribe` endpoint
# - [ ] Install faster-whisper, load `small` model at startup
# - [ ] Accept mp3/wav upload, run Whisper, return text in response
# - [ ] Basic input validation (file type, size)
# - [ ] Test with curl: `curl -X POST /transcribe -F "file=@clip.mp3"`


model_size = 'small'


app = FastAPI()

@app.post('/transcribe')
async def transcribe(file: UploadFile): #here we get a file
    file_name = file.filename
    file_size = file.size
    file_headers = file.headers
    content_type = file.content_type # we need this one
    return {
        "file_name": file_name,
        "file_size": file_size,
        "file_headers": file_headers,
        "file_content_type": content_type,
    }