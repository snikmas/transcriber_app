from fastapi import HTTPException
from src.constants import Job_Status
import uuid
from pathlib import Path
from datetime import datetime
import queue

# jere queue managment. ok
jobs = {}
queue = queue.Queue()


# or async?

def create_job(file_path: Path, filename:str, source_family: str) -> dict:
    uuid_id = uuid.uuid4()
    job = {
        "filename": filename,
        "status": Job_Status.QUEUED,
        "path": file_path,
        "source": source_family,
        "created_at": datetime.now()
        
    }

    jobs[uuid_id] = job
    queue.put(jobs)
    return job


def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404)
    return {"job_id": job_id, **job} # ** - unpacking here

def update_status(job_id: str, status: Job_Status):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404)
    job['status'] = status