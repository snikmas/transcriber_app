from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4", ".webm"}
SUPPORTED_SUFFIXES = AUDIO_SUFFIXES | VIDEO_SUFFIXES

SUPPORTED_CONTENT_TYPES = {
    "application/octet-stream",
    "audio/aac",
    "audio/flac",
    "audio/m4a",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/opus",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
    "audio/x-wav",
    "video/avi",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
}
