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
        source_family: str, # required parameter - the first 
        filepath: Path | None = None,
        filename:str | None = None, 
        file_type: str | None  = None, 
        is_url: str | None  = None
        ) -> str:
    
    with lock: 
        uuid_id = uuid.uuid4()
        job = {
            "filename": filename,
            "file_type": file_type,
            "status": Job_Status.QUEUED.value,
            "filepath": filepath,
            "source_family": source_family,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_url": is_url,
            'result': None
        }
        all_jobs[str(uuid_id)] = job
        cur_queue.put(str(uuid_id)) # need only its id
    logging.info(f"JOB PARAMS: {job}\n\n")
    # have to do try/except?   
    database.add_job(job_id=str(uuid_id), job=job, result=None)

    return str(uuid_id)



def get_job(job_id: str) -> dict:

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        return {"job_id": job_id, **job} # ** - unpacking here


def update_status(job_id: str, status: Job_Status) -> None:

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        job['status'] = status.value
    database.update_job(job_id=job_id, status=status.value)


def delete_job(job_id: str) -> None:
    
    with lock:
        job = all_jobs.pop(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
    database.delete_job(job_id)
        
        
    logging.info("the key was deleted")


def get_result(job_id: str) -> dict:
    with lock:
        try:
            job = all_jobs.get(job_id)
            if job is None:
                raise KeyError(f"Job {job_id} not found")
        except KeyError:
            raise KeyError('[jobs]: no key')

    return job.get('result')