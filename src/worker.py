from src.jobs import queue
import src.parsers as parsers
import jobs

from fastapi import HTTPException
import src.constants as const


# too many logic?
def worker():
    while True:
        job = queue.get()

        jobs.update_status(job.get("job_id"), const.Job_Status.PROCESSING)

        path = job.get("path")
        source_family = job.get("source")

        res, info = parsers.transcribe_file(path)

        # path in the job -> 
        res_parse_cli = parsers.parsed_res(res, info, job.get("filename"))

        # another logic: preapring a response
        if source_family in const.CLI_REQUESTS:
            job['content'] = res_parse_cli
        elif source_family in const.BROWSER_REQUESTS:
            file = parsers.parse_to_file(res_parse_cli)
            job['content'] = res_parse_cli
            job['download_url'] = file
        else:
            jobs.update_status(job.get('job_id'), const.Job_Status.FAILED)
            raise HTTPException(status_code=403, detail='Forbidden')
        

        jobs.update_status(job.get('job_id'), const.Job_Status.DONE)
