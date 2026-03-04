from fastapi import FastAPI, UploadFile, Request, HTTPException, Response, status
from user_agents import parse
from contextlib import asynccontextmanager

import logging
import os
import threading
os.environ["HF_HUB_OFFLINE"] = "1" # the model in the parser, have to tell it: it should run offline

from src.constants import BROWSER_REQUESTS, CLI_REQUESTS, Job_Status, ALLOWED_VIDEO_TYPES, ALLOWED_AUDIO_TYPES
import src.parsers as parsers
import src.utils as utils
import src.jobs as jobs
import src.worker as worker

logging.basicConfig(level=logging.INFO)

# WORKER
@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs right now
    thread = threading.Thread(target=worker.worker, daemon=True)
    thread.start()
    yield
    

app = FastAPI(lifespan=lifespan)


@app.get('/favicon.ico', include_in_schema=False)
async def flavicon():
    return Response(status_code=204)



@app.get('/transcribe/{job_id}', status_code=200)
async def get_transcribe_res(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    match job.get('status'):
        case Job_Status.PROCESSING.value:
            return {"message": "in process..."}
        case Job_Status.QUEUED.value:
            return {"message": "is queued"}
        case Job_Status.FAILED.value:
            return {"message": "the process is failed"}
            pass
        case Job_Status.DONE.value:
            if job.get("source") in CLI_REQUESTS:
                return {"content": job.get('content'), "download_url": job.get('download_url')} # or just put the last 2 lines frmo the dict?
            else:
                return {"content": job.get("content")}
            # needs to delete from hte jobs?



@app.post('/transcribe', status_code=201) # here we create a job
async def transcribe(
    request: Request, 
    response: Response,
    file: UploadFile | None = None,
    url: str | None = None,  # have to do only on
    ): 

    if not url and not file or url and file :
        raise HTTPException(status_code=404, detail="You must provide a file or a url")

    # 1. determine from there the request was send
    user_agent_header = request.headers.get('user-agent')
    user_agent = parse(user_agent_header)

    source_family = user_agent.browser.family
    
    if file:
        content_type = await utils.determine_type(file)
        is_url = None
    elif url: #cant check the content tpye...
        logging.info("its an url")
        is_url = url
        content_type = None
         
    
    # later add a link + divide: for video you need to extract the audio
    if content_type and is_url is None:
    
        if ALLOWED_VIDEO_TYPES: 
            content_type = ALLOWED_VIDEO_TYPES.get(content_type)
        # 2. save to the disk
        try:
            file_path = parsers.save_file(file)
        except:
            response.status_code = status.HTTP_400_BAD_REQUEST
            raise Exception("Error during saving a file")
        jobs_id = jobs.create_job(file_path, file.filename, source_family, content_type, is_url) #im not sure is it a str or enum. 
    elif is_url is None: #means that this is a file and we cant support it
        response.status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        raise HTTPException(status_code=415, detail={"message": f"{content_type} doesn't supported"})
    # 3. create a job IS NTO THE BEST PLASE
    else: #it's an url
        jobs_id = jobs.create_job(None, None, source_family, None, is_url=is_url) 
    
    logging.info("Job created")
    return jobs_id

@app.get("/jobs", status_code=200)
async def get_all_jobs():
    all_jobs = jobs.all_jobs

    return all_jobs