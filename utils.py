from datetime import datetime
import pytz


def get_madrid_time():
    """
    Get the current time in Madrid timezone.

    Returns:
        datetime: The current time in Madrid timezone
    """
    return datetime.now(pytz.timezone("Europe/Madrid"))


def unix_to_madrid_time(unix_timestamp):
    """
    Convert a Unix timestamp to Madrid time.

    Args:
        unix_timestamp (int): The Unix timestamp to convert

    Returns:
        datetime: The corresponding datetime in Madrid timezone
    """
    utc_time = datetime.utcfromtimestamp(unix_timestamp)
    utc_time = utc_time.replace(tzinfo=pytz.UTC)
    return utc_time.astimezone(pytz.timezone("Europe/Madrid"))
