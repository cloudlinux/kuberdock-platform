# -*- coding: utf-8 -*-
import time
from datetime import datetime
from flask import current_app

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
