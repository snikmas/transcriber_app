import src.parsers as parsers
import src.jobs as jobs
import src.utils as utils
import src.constants as const
import logging
import extractor
import src.transcriber as transcriber 


def worker():
    while True:
        job_id = jobs.cur_queue.get()
        with jobs.lock:
            job = jobs.all_jobs[job_id]
        jobs.update_status(job_id, const.Job_Status.PROCESSING)
        logging.info(f'source family: {job.get('source_family')}')

        if job.get('is_url') is None:
            path = job.get("path")
            
            logging.info('preapring to transcribe') 
            try:
                res, info = transcriber.transcribe_file(path)
                
                result_json = parsers.parsed_res(res, info, job.get("filename"))
    
            except Exception as e:
                job['status'] = const.Job_Status.FAILED.value
                logging.error(f'[WORKER]: {e}')
                continue

        else: # is a url
            try:
                id = utils.parsing_url(job.get('is_url'))  
            
                subtitles_json = extractor.get_subtitles(id)
                video_info = extractor.get_video_info(id)
            except Exception as e:
                logging.error(f'[WORKER]: problem with parsing / getting subtitles/video info')
                job['status'] = const.Job_Status.FAILED.value
                continue
            try:
                result_json = video_info | subtitles_json
            except ValueError:
                logging.error(f'[WORKER]: {ValueError}')
                job['status'] = const.Job_Status.FAILED.value
                continue
            except NameError:
                logging.error(f'[WORKER]: {NameError}')
                job['status'] = const.Job_Status.FAILED.value
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

        jobs.update_status(job_id, const.Job_Status.DONE)
