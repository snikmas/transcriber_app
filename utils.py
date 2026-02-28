from datetime import timedelta
from pathlib import Path
from fastapi import UploadFile

def formatting_seconds(seconds: int) -> str:
    # timedelta takes seconds as an argument
    total_seconds = int(round(seconds))
    clean_time = timedelta(seconds=total_seconds)
    return str(clean_time)

def convert_to_uploadfile(parsed_res_info: Path) -> UploadFile:
    with open (parsed_res_info, 'rb'):
        upload_file = UploadFile(
            file = parsed_res_info,
            filename=parsed_res_info.name,
            size=parsed_res_info.stat().st_size
            )
        
    return upload_file