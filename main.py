from fastapi import FastAPI, UploadFile, Request, HTTPException, Response
from faster_whisper import WhisperModel
from user_agents import parse
from contextlib import asynccontextmanager

from datetime import timedelta
from pathlib import Path
import logging
import os
import threading

from src.constants import ALLOWED_TYPES, BROWSER_REQUESTS, CLI_REQUESTS, Job_Status
import src.parsers as parsers
import src.utils as utils
import src.jobs as jobs
import src.worker as worker

os.environ["HF_HUB_OFFLINE"] = "1"
logging.basicConfig(level=logging.INFO)



# WORKER
@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs right now
    thread = threading.Thread(worker.worker, daemon=True)
    worker.worker()

    yield
    


app = FastAPI(lifespan=lifespan)



@app.get('/favicon.ico', include_in_schema=False)
async def flavicon():
    return Response(status_code=204)



@app.get('/transcribe/{job_id}')
async def get_transcribe_res(job_id: int):
    job = jobs.get_job(job_id)
    match job.get('status'):
        case Job_Status.PROCESSING.value:
            pass
        case Job_Status.FAILED.value:
            pass
        case Job_Status.DONE.value:
            if job.get("source") in CLI_REQUESTS:
                return {"content": job.get('content'), "download_url": job.get('download_url')} # or just put the last 2 lines frmo the dict?
            else:
                return {"content": job.get("content")}
            # needs to delete from hte jobs?
            


@app.post('/transcribe') # here we create a job
async def transcribe(request: Request, file: UploadFile): 

    # 1. determine from there the request was send
    user_agent_header = request.headers.get('user-agent')
    user_agent = parse(user_agent_header)

    source_family = user_agent.browser.family
    
    content_type = await utils.determine_type(file)

    # later add a link + divide: for video you need to extract the audio
    if content_type in ALLOWED_TYPES:
        
        # 2. save to the disk
        try:
            file_path = parsers.save_file(file)
        except:
            raise Exception("Error during saving a file")
    
        # 3. create a job
        jobs.create_job(file_path, file.filename, source_family)
        logging.info("Job created")

    else:
        raise HTTPException(status_code=415, detail={"message": f"{content_type} doesn't supported"})

