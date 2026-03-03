import src.parsers as parsers
import src.jobs as jobs

import src.constants as const
import logging


# too many logic?
def worker():
    while True:
        job_id = jobs.queue.get()
        job = jobs.all_jobs[job_id]
        jobs.update_status(job_id, const.Job_Status.PROCESSING)

        path = job.get("path")
        source_family = job.get("source")

        try:
            res, info = parsers.transcribe_file(path)
        except Exception as e:
            jobs.update_status(job_id, const.Job_Status.FAILED)
            logging.error("Tranctiption failed job %s: %s", job_id, e)
            continue
        
        # path in the job -> 
        res_parse_cli = parsers.parsed_res(res, info, job.get("filename"))

        # another logic: preapring a response. change it
        if source_family in const.CLI_REQUESTS:
            job['content'] = res_parse_cli
        elif source_family in const.BROWSER_REQUESTS:
            file = parsers.parse_to_file(res_parse_cli)
            job['content'] = res_parse_cli
            job['download_url'] = file
        else:
            jobs.update_status(job_id, const.Job_Status.FAILED)
            logging.error("The request is not in CLI/BROWSERS types")
            continue    

        jobs.update_status(job_id, const.Job_Status.DONE)
