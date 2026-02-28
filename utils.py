from datetime import timedelta

def formatting_seconds(seconds) -> str:
    # timedelta takes seconds as an argument
    total_seconds = int(round(seconds))
    clean_time = timedelta(seconds=total_seconds)
    return str(clean_time)