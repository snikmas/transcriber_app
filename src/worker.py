import src.parsers as parsers
import src.jobs as jobs
import src.utils as utils
import src.constants as const
import logging
import extractor
import src.transcriber as transcriber 
from src.jobs import lock

import src.database.database as database

def worker():
    while True:
        job_id = jobs.cur_queue.get()
        with jobs.lock:
            job = jobs.all_jobs[job_id]
        jobs.update_status(job_id, const.Job_Status.PROCESSING)
        logging.info(f'source family: {job.get('source_family')}')

        if job.get('is_url') is None:
            path = job.get("filepath")
            
            logging.info('preapring to transcribe') 
            try:
                res, info = transcriber.transcribe_file(path)
                
                result_json = parsers.parsed_res(res, info, job.get("filename"))
    
            except Exception as e:
                with lock:
                    job['status'] = const.Job_Status.FAILED.value
                database.update_job(job_id=job_id, status=const.Job_Status.FAILED.value)
                logging.error(f'[WORKER]: {e}')
                continue

        else: # is a url
            try:
                id = utils.parsing_url(job.get('is_url'))  
            
                subtitles_json = extractor.get_subtitles(id)
                video_info = extractor.get_video_info(id)
            except Exception as e:
                logging.error(f'[WORKER]: problem with parsing / getting subtitles/video info')
                with lock:
                    job['status'] = const.Job_Status.FAILED.value
                jobs.update_status(job_id=job_id, status=const.Job_Status.FAILED.value)
                continue
            try:
                result_json = video_info | subtitles_json
            except ValueError:
                logging.error(f'[WORKER]: {ValueError}')
                with lock:
                    job['status'] = const.Job_Status.FAILED.value
                jobs.update_status(job_id=job_id, status=const.Job_Status.FAILED.value)
                continue
            except NameError:
                logging.error(f'[WORKER]: {NameError}')
                with lock: # does it make sense changing here by ahnd and not to do jobs,update status? ith ink no. + there you can do db update
                    job['status'] = const.Job_Status.FAILED.value
                jobs.update_status(job_id=job_id, status=const.Job_Status.FAILED.value)
                continue

            

        with jobs.lock:

            logging.info(f'source family: {job.get('source_family')}')
        
            if job.get('source_family') in const.CLI_REQUESTS:
                job['result'] = result_json
            elif job.get('source_family') in const.BROWSER_REQUESTS:
                file = parsers.parse_to_file(full_info=result_json)
                job['result'] = result_json
                job['download_url'] = file
            else:
                logging.error("[WORKER] The request is not in CLI/BROWSERS types")
                job['result'] = None
                job['status'] = const.Job_Status.FAILED.value # have to change it here, cuz of deadlockoo
                continue    

        with lock: # if jobs,upate status is changing it.. 
            jobs.update_status(job_id, const.Job_Status.DONE)
