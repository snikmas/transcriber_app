from fastapi import FastAPI, UploadFile, Request, HTTPException, Response
from faster_whisper import WhisperModel
from user_agents import parse
from contextlib import asynccontextmanager

from datetime import timedelta
from pathlib import Path
import logging
import os

from src.constants import ALLOWED_TYPES, BROWSER_REQUESTS, CLI_REQUESTS, Job_State
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
    worker.worker()

    #runs after temrinating the project
    yield
    





app = FastAPI(lifespan=lifespan)



@app.get('/favicon.ico', include_in_schema=False)
async def flavicon():
    return Response(status_code=204)



@app.get('/transcribe/{job_id}')
async def get_transcribe_res(job_id: int):
    pass



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
        jobs.create_job(file_path)
        logging.info("Job created")


        # res, info = parsers.transcribe_file(file) not here
    else:
        raise HTTPException(status_code=415, detail={"message": f"{content_type} doesn't supported"})

    res_parse_cli = parsers.parsed_res(res, info, file.filename)
    if source_family in CLI_REQUESTS:
        return res_parse_cli
    elif source_family in BROWSER_REQUESTS:
        file = parsers.parse_to_file(res_parse_cli)
        return {
            "content": res_parse_cli,
            "download_url": file
        }
    else:
        raise HTTPException(status_code=403, detail='Forbidden')


