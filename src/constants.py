from enum import Enum

class Job_Status(Enum):
    FAILED = "failed"
    DONE = "done"
    PROCESSING = "processing"
    QUEUED = "queued"


ALLOWED_AUDIO_TYPES = {
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/aac": "aac",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/opus": "opus",
    "audio/amr": "amr",
    "audio/aiff": "aiff",
    "audio/x-aiff": "aiff",
    "audio/x-ms-wma": "wma",
    "audio/ac3": "ac3",

}

ALLOWED_VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/x-matroska": "mkv",
    "video/x-flv": "flv",
    "video/x-ms-wmv": "wmv"
}

BROWSER_REQUESTS = {
    'Chrome': 'Chrome',
    'Chrome Mobile': 'Chrome',
    'Firefox' : 'Firefox',
    'Firefox Mobile': 'Firefox',
    'Safari Mobile': 'Safari',
    'Safari': 'Safari',
    'Edge': 'Edge',
}

CLI_REQUESTS = {
    'curl': 'curl',
    'python-requests': 'python-requests',
    'PostmanRuntime': 'PostmanRuntime',
}