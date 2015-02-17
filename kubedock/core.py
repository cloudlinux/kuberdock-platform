from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.influxdb import InfluxDB
from flask.ext.login import LoginManager
from flask import current_app
from sse import Sse
import redis
import json
import paramiko
from paramiko import ssh_exception
import socket
from .settings import DEBUG, NODE_SSH_AUTH
from rbac import check_permission

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'

db = SQLAlchemy()
influx_db = InfluxDB()


class AppError(Exception):
    """Base application error class."""
    def __init__(self, msg):
        self.msg = msg


class ConnectionPool(object):
    pool = {}

    @classmethod
    def key(cls, *args, **kwargs):
        return ':'.join(args) + \
            ':'.join('%s=%s' % (k, v) for k, v in kwargs.items())

    @classmethod
    def lookup_pool(cls, *args, **kwargs):
        key = cls.key(*args, **kwargs)
        if key not in cls.pool:
            cls.pool[key] = redis.ConnectionPool(*args, **kwargs)
        return cls.pool[key]

    @classmethod
    def get_connection(cls):
        pool = cls.lookup_pool(
            host=current_app.config.get('SSE_REDIS_HOST', '127.0.0.1'),
            port=current_app.config.get('SSE_REDIS_PORT', 6379),
            db=current_app.config.get('SSE_REDIS_DB', 0),
        )
        return redis.StrictRedis(connection_pool=pool)


class EvtStream(object):
    def __init__(self, conn, channel):
        self.pubsub = conn.pubsub()
        self.pubsub.subscribe(channel)

    def __iter__(self):
        ssev = Sse()
        for data in ssev:
            yield data.encode('u8')
        for message in self.pubsub.listen():
            if message['type'] == 'message':
                event, data = json.loads(message['data'])
                ssev.add_message(event, data)
                for data in ssev:
                    yield data.encode('u8')


def ssh_connect(host, timeout=10):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    error_message = None
    try:
        if DEBUG:
            ssh.connect(hostname=host, username='root',
                        password=NODE_SSH_AUTH, timeout=timeout)
        else:
            ssh.connect(hostname=host, username='root',
                        key_filename=NODE_SSH_AUTH, timeout=timeout)
    except ssh_exception.AuthenticationException as e:
        error_message =\
            '{0} Check hostname, your credentials, and try again'.format(e)
    except socket.timeout:
        error_message = 'Connection timeout. Check hostname and try again'
    except socket.error as e:
        error_message =\
            '{0} Check hostname, your credentials, and try again'.format(e)
    return ssh, error_message