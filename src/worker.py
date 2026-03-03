import src.parsers as parsers
import src.jobs as jobs

import src.constants as const
import logging
import threading


def worker():
    while True:
        job_id = jobs.cur_queue.get()
        with jobs.lock:
            job = jobs.all_jobs[job_id]
        jobs.update_status(job_id, const.Job_Status.PROCESSING)

        path = job.get("path")
        source_family = job.get("source")

        try:
            res, info = parsers.transcribe_file(path)
        except Exception as e:
            jobs.update_status(job_id, const.Job_Status.FAILED)
            logging.error("[WORKER] Tranctiption failed job %s: \n%s", job_id, e)
            continue
        
        # path in the job -> 
        res_parse_cli = parsers.parsed_res(res, info, job.get("filename"))

        # another logic: preapring a response. change it

        with jobs.lock:
            if source_family in const.CLI_REQUESTS:
                job['content'] = res_parse_cli
            elif source_family in const.BROWSER_REQUESTS:
                file = parsers.parse_to_file(res_parse_cli)
                job['content'] = res_parse_cli
                job['download_url'] = file
            else:
                logging.error("[WORKER] The request is not in CLI/BROWSERS types")
                job['status'] = const.Job_Status.FAILED.value # have to change it here, cuz of deadlockoo
                continue    

        jobs.update_status(job_id, const.Job_Status.DONE)
