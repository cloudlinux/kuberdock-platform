# -*- coding: utf-8 -*-
import time
from datetime import datetime
from functools import wraps

from flask import current_app
from pytz import common_timezones, timezone

from ..core import ConnectionPool


def mark_online(user_id):
    now = int(time.time())
    expires = now + (current_app.config['ONLINE_LAST_MINUTES'] * 60) + 10
    all_users_key = 'online-users/%d' % (now // 60)
    user_key = 'user-activity/%s' % user_id
    redis = ConnectionPool.get_connection()
    p = redis.pipeline()
    p.sadd(all_users_key, user_id)
    p.set(user_key, now)
    p.expireat(all_users_key, expires)
    p.expireat(user_key, expires)
    p.execute()


def get_user_last_activity(user_id):
    redis = ConnectionPool.get_connection()
    last_active = redis.get('user-activity/%s' % user_id)
    if last_active is None:
        return None
    return datetime.utcfromtimestamp(int(last_active))


def get_online_users():
    current = int(time.time()) // 60
    minutes = xrange(current_app.config['ONLINE_LAST_MINUTES'])
    redis = ConnectionPool.get_connection()
    return redis.sunion(['online-users/%d' % (current - x)
                         for x in minutes])


def append_offset_to_timezone(tz):
    """Appends offset value to timezone string:
    Europe/London -> Europe/London (+000)
    """
    if tz not in common_timezones:
        return tz
    offset = datetime.now(timezone(tz)).strftime('%z')
    return '{0} ({1})'.format(tz, offset)


def strip_offset_from_timezone(tz):
    """Clears timezone string - removes UTC offset from timezone string:
    Europe/London (+000) -> Europe/London
    """
    if not isinstance(tz, basestring):
        return tz
    return tz.split(' (')[0].strip()


def enrich_tz_with_offset(timezone_keys):
    """Decorator appends offset to valid timezone fields in result dict of
    decorated function.
    :param timezone_keys: list of fields which must be treated as timezones
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwds):
            res = f(*args, **kwds)
            if not isinstance(res, dict):
                return res
            for key in timezone_keys:
                value = res.get(key, None)
                if value is None:
                    continue
                res[key] = append_offset_to_timezone(value)
            return res
        return wrapper
    return decorator

