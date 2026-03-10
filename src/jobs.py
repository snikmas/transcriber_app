from fastapi import HTTPException
from src.constants import Job_Status
import uuid
from pathlib import Path
from datetime import datetime, timezone
import queue
import threading

import logging

all_jobs = {}
cur_queue = queue.Queue()

lock = threading.Lock()

def create_job(
        file_path: Path | None, 
        filename:str | None, 
        source_family: str, 
        file_type: str | None, 
        is_url: str | None) -> str:
    
    with lock: # is it required?
        uuid_id = uuid.uuid4()
        job = {
            "filename": filename,
            "file_type": file_type,
            "status": Job_Status.QUEUED.value,
            "filepath": file_path,
            "source_family": source_family,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_url": is_url
        }
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
            raise ValueError(f"No such kind of job")
        job['status'] = status.value