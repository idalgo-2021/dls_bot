import time


def format_duration(start_time: float) -> str:
    """Formats the time difference into a human-readable string."""
    duration_seconds_total = int(time.monotonic() - start_time)
    minutes, seconds = divmod(duration_seconds_total, 60)
    if minutes > 0:
        return f"{minutes} мин. {seconds} сек."
    return f"{seconds} сек."
