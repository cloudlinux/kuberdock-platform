import re
import time

IP_PATTERN = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')

TIME_FORMATS = [
    '%Y-%m-%d',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d %H:%M:%S'
]


def timestamp(date_str):
    for fmt in TIME_FORMATS:
        try:
            struct_time = time.strptime(date_str, fmt)
        except ValueError:
            continue
        return int(time.mktime(struct_time))
    raise ValueError(
        "time data '{date}' does not match any acceptable format ({formats})"
        .format(
            date=date_str,
            formats=', '.join("'%s'" % tf for tf in TIME_FORMATS)))
