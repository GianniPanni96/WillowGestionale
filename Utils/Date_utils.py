from datetime import datetime

DB_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")

def parse_db_datetime(date_str):
    if not date_str:
        return None

    for fmt in DB_DATETIME_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None