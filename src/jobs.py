from fastapi import HTTPException
from src.constants import Job_Status
import uuid
from pathlib import Path
from datetime import datetime
import queue
import threading

import logging
# jere queue managment. ok
all_jobs = {}
# how to use lock here?
cur_queue = queue.Queue()

lock = threading.Lock()

# or async?
# if isUrl: url or file
def create_job(
        file_path: Path | None, 
        filename:str | None, 
        source_family: str, 
        file_type: str | None, 
        is_url: str | None) -> dict:
    # lock()
    uuid_id = uuid.uuid4()
    job = {
        "filename": filename,
        "file_type": file_type,
        "status": Job_Status.QUEUED.value,
        "path": file_path,
        "source": source_family,
        "created_at": datetime.now()
        
    }
    if is_url:
        job['is_url'] = is_url
    # with lock:
    all_jobs[str(uuid_id)] = job
    cur_queue.put(str(uuid_id)) # need only its id
    return uuid_id



def get_job(job_id: str) -> dict:

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            logging.error('[JOBS]: cannot find the job, get_job')
            raise HTTPException(404)
        return {"job_id": job_id, **job} # ** - unpacking here

def update_status(job_id: str, status: Job_Status):

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            logging.error('[JOBS]: cannot find the job, update_status')
            raise HTTPException(404)
        job['status'] = status.value