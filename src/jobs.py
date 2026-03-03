from fastapi import HTTPException
from src.constants import Job_Status
import uuid
from pathlib import Path
from datetime import datetime
import queue
import threading

# jere queue managment. ok
all_jobs = {}
# how to use lock here?
queue = queue.Queue()

lock = threading.Lock()

# or async?

def create_job(file_path: Path, filename:str, source_family: str) -> dict:
    # lock()
    uuid_id = uuid.uuid4()
    job = {
        "filename": filename,
        "status": Job_Status.QUEUED.value,
        "path": file_path,
        "source": source_family,
        "created_at": datetime.now()
        
    }
    with lock:
        all_jobs[str(uuid_id)] = job
    queue.put(str(uuid_id)) # need only its id
    return uuid_id



def get_job(job_id: str) -> dict:

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            raise HTTPException(404)
        return {"job_id": job_id, **job} # ** - unpacking here

def update_status(job_id: str, status: Job_Status):

    with lock:
        job = all_jobs.get(job_id)
        if job is None:
            raise HTTPException(404)
        job['status'] = status.value