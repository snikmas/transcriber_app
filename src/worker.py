import src.parsers as parsers
import src.jobs as jobs
import src.utils as utils
import src.constants as const
import logging
import extractor
from extractor import get_subtitles


def worker():
    while True:
        logging.info("in worker")
        job_id = jobs.cur_queue.get()
        with jobs.lock:
            job = jobs.all_jobs[job_id]
        jobs.update_status(job_id, const.Job_Status.PROCESSING)

        if 'is_url' not in job:
            path = job.get("path")
            source_family = job.get("source") #safier than do job['source]

            if job.get('file_type') in const.ALLOWED_VIDEO_TYPES:
                path = extractor.extract_audio(path)

                try:
                    res, info = parsers.transcribe_file(path)
                except Exception as e:
                    jobs.update_status(job_id, const.Job_Status.FAILED)
                    logging.error("[WORKER] Tranctiption failed job %s: \n%s", job_id, e)
                    continue
            
            # path in the job -> 
                res_parse_cli = parsers.parsed_res(res, info, job.get("filename"))
            logging.info("is job in job")
        elif 'is_url' in job:
            logging.info(f"preparing for parsing..{job.get('is_url')}")
            id = utils.pasring_url(job.get('is_url'))
            
            # this thing actually would download the thing
            video_subs = get_subtitles(id)
            # save to fild? it get path
            
            
            # subtitles = get_subtitles(video_info.get('id'))
            
            logging.info(f"VIDEO_INFO RESULTS (the last logging)")
            # for key in video_info.keys():
                # logging.info(f"{key}: {video_info.get(key)}")
        

        # maybe put it under the job
        
        # another logic: preapring a response. change it

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
