from datetime import timedelta
from pathlib import Path
from fastapi import UploadFile
import magic
from src.constants import ALLOWED_AUDIO_TYPES, ALLOWED_VIDEO_TYPES

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


async def determine_type(file: UploadFile) -> str:

    buffer = await file.read(2048)
    await file.seek(0)
    mime_type =  magic.from_buffer(buffer, mime=True)
    if mime_type in ALLOWED_VIDEO_TYPES: return ALLOWED_VIDEO_TYPES.get(mime_type)
    elif mime_type in ALLOWED_AUDIO_TYPES: return ALLOWED_AUDIO_TYPES.get(mime_type)
    else: return None




