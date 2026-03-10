from fastapi import HTTPException
from src.constants import Job_Status
import uuid
from pathlib import Path
from datetime import datetime, timezone
import queue
import threading
import src.database.database as database

import logging

all_jobs = {}
cur_queue = queue.Queue()

lock = threading.Lock()
# we don't delete a job? do history?
def create_job(
        file_path: Path | None, 
        filename:str | None, 
        source_family: str, 
        file_type: str | None, 
        is_url: str | None) -> str:
    
    with lock: 
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

    # have to do try/except?   
    database.add_job(job_id=str(uuid_id), job=job, result=None)

    return str(uuid_id)



def get_job(job_id: str) -> dict:

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            logging.error('[JOBS]: cannot find the job, get_job')
            raise HTTPException(404)
        return {"job_id": job_id, **job} # ** - unpacking here


def update_status(job_id: str, status: Job_Status) -> None:

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            logging.error('[JOBS]: cannot find the job, update_status')
            raise ValueError(f"No such kind of job")
        job['status'] = status.value
    database.update_job(job_id=job_id, status=status.value)


def delete_job(job_id: str) -> None:
    
    with lock:
        try:
            removed_job = all_jobs.pop(job_id)
        except KeyError:
            logging.error(f"[jobs]: no key {KeyError}")
            raise KeyError
    database.delete_job(job_id)
        
        
    logging.info("the key was deleted")


def get_result(job_id: str) -> dict:
    with lock:
        res = all_jobs.get(job_id)
    if res is None:
        raise KeyError('[jobs]: no key')

    return res.get('result')