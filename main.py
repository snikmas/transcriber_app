from fastapi import FastAPI, UploadFile, Request, HTTPException, Response, status
from user_agents import parse
from contextlib import asynccontextmanager

import logging
import os
import threading
os.environ["HF_HUB_OFFLINE"] = "1" # the model in the parser, have to tell it: it should run offline

from src.constants import CLI_REQUESTS, Job_Status, ALLOWED_VIDEO_TYPES, ALLOWED_AUDIO_TYPES
import src.parsers as parsers
import src.utils as utils
import src.jobs as jobs
import src.worker as worker
import extractor
import src.database.database as database

logging.root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
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
        case Job_Status.DONE.value:
            if job.get("source_family") in CLI_REQUESTS:
                return {"result": job.get('result'), "download_url": job.get('download_url')} # or just put the last 2 lines frmo the dict?
            else:
                return {"result": job.get("result")} # needs to delete from hte jobs?


@app.post('/transcribe', status_code=201) 
async def transcribe(
    request: Request, 
    response: Response,
    file: UploadFile | None = None,
    url: str | None = None,  
    ): 
    logging.info("in transcribe")

    if bool(url) == bool(file) :
        raise HTTPException(status_code=400, detail="You must provide a file or a url")

    # 1. determine from there the request was send
    user_agent_header = request.headers.get('user-agent')
    user_agent = parse(user_agent_header)

    source_family = user_agent.browser.family
    logging.info(source_family)
    

    if file:
        if source_family in CLI_REQUESTS:
            file_type = await utils.determine_type(file)
        else: 
            file_type = await utils.determine_type(file)
        filename = file.filename

        if file_type is not None:
            try:
                file_path = parsers.save_file(file)
                if file_type in ALLOWED_VIDEO_TYPES.values():
                    file_path = extractor.extract_audio(file_path)
            except Exception:
                response.status_code = status.HTTP_400_BAD_REQUEST
                raise HTTPException(status_code=500, detail="Error saving a file")

            

        else: 
            response.status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE 
            raise HTTPException(status_code=415, detail={"message": f"{file_type} doesn't supported"})
    elif url: 
        file_type = None
        filename = None
        file_path = None
    else: 
        raise HTTPException(status_code=400, detail={'message': 'No url, no file in the request'})
                
    jobs_id = jobs.create_job(
        file_path=file_path, 
        filename=filename, 
        source_family=source_family, 
        file_type=file_type, 
        is_url=url
        )
        

    
    logging.info("Job created")
    return {"jobs_id": jobs_id}

@app.get("/jobs", status_code=200)
async def get_all_jobs():
    all_jobs = jobs.all_jobs

    return all_jobs

@app.delete("/jobs/{job_id}", status_code=200)
async def delete_job(job_id: str, response: Response):
    try:
        jobs.delete_job(job_id=job_id)
    except KeyError:
        response.status_code=status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=404, detauil={"message": "no key"})
    
@app.get('/jobs/{job_id}/result', status_code=200)
async def get_result(job_id: str, response: Response):
    try:
        result = jobs.get_result(job_id)
    except Exception:
        response.status_code=status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=404, detail=f"[main] No key found")
    
    return result