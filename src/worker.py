import src.parsers as parsers
import src.jobs as jobs
import src.utils as utils
import src.constants as const
import logging
import extractor
import src.transcriber as transcriber
from extractor import get_subtitles


def worker():
    while True:
        job_id = jobs.cur_queue.get()
        with jobs.lock:
            job = jobs.all_jobs[job_id]
        jobs.update_status(job_id, const.Job_Status.PROCESSING)

        if job.get('is_url') is None:
            path = job.get("path")
            source_family = job.get("source")
            
            logging.info('preapring to transcribe') 
            try:
                if job.get('file_type') in const.ALLOWED_VIDEO_TYPES:
                    path = extractor.extract_audio(path)

                res, info = transcriber.transcribe_file(path)
                logging.info(f"RES\n{res}\n\n INFO: \n{info}\n\n")
                
                logging.info('WORKER: PREAPRING FOR RES_PARSE_CLI') #no need to parse? just save dict
                res_parse_cli = parsers.parsed_res(res, info, job.get("filename"))

                
            except Exception as e:
                logging.error(f'ERROR IN woekr: {e}')

        elif job.get('is_url') is not None:
            logging.info(f"IS URL IN JOB")
            logging.info(f"preparing for parsing..{job.get('is_url')}")
            id = utils.pasring_url(job.get('is_url'))  
            
            # this thing actually would download the ting
            video_subs = get_subtitles(id)
            

        with jobs.lock:

            if 'is_url' in job:
                pass
                # job['video_info'] = video_info
            else:
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
