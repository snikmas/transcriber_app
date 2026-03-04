from pathlib import Path
import ffmpeg
import logging

def extract_audio(temp_file: Path) -> Path:

    output_path = temp_file.with_suffix('wav') #idk how to handle it?
    try:
        #if we handle only one file for time, its okay. but later if 2+ files -> problems
        ffmpeg.input(str(temp_file)).output(str(output_path), acodec='pcm_s16le', ar=16000, ac=1).run(overwrite_output=True, quiet=Tru)
        return output_path
    except ffmpeg.Error as e:
        logging.error("[EXTRACTOR] ffmpeg error: %s", e.stderr.decode())    
        raise e