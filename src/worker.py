import src.parsers as parsers
import src.jobs as jobs
import src.utils as utils
import src.constants as const
import logging
import extractor
import src.transcriber as transcriber
import extractor 


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
                if job.get('file_type') in const.ALLOWED_VIDEO_TYPES: #cuz if its a video - have to do more
                    path = extractor.extract_audio(path)

                res, info = transcriber.transcribe_file(path)
                
                result_json = parsers.parsed_res(res, info, job.get("filename"))
    
            except Exception as e:
                logging.error('[WORKER]: {e}')

        else: # is a url
            id = utils.pasring_url(job.get('is_url'))  
            
            subtitles_json = extractor.get_subtitles(id)
            video_info = extractor.get_video_info(id)

            result_json = video_info | subtitles_json
            

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
                job['status'] = const.Job_Status.FAILED.value # have to change it here, cuz of deadlockoo
                continue    

        jobs.update_status(job_id, const.Job_Status.DONE)
