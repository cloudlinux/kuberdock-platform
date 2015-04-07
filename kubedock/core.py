import json
import paramiko
import redis
import socket
from sse import Sse
from paramiko.ssh_exception import AuthenticationException, SSHException
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.influxdb import InfluxDB
from flask.ext.login import LoginManager
from flask import current_app
from werkzeug.contrib.cache import RedisCache


from .settings import REDIS_HOST, REDIS_PORT


login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'

db = SQLAlchemy()
influx_db = InfluxDB()
cache = RedisCache(host=REDIS_HOST, port=REDIS_PORT)


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
        ssh.connect(host, username='root', timeout=timeout)
    except (AuthenticationException, SSHException) as e:
        error_message =\
            '{0}.\nCheck hostname, check that user from which '.format(e) +\
            'Kuberdock runs (usually nginx) has ability to login as root on ' +\
            'this node, and try again'
    except socket.timeout:
        error_message = 'Connection timeout. Check hostname and try again'
    except socket.error as e:
        error_message =\
            '{0} Check hostname, your credentials, and try again'.format(e)
    return ssh, error_message


def fast_cmd(ssh, cmd):
    i, o, e = ssh.exec_command(cmd)
    s = o.channel.recv_exit_status()
    if s != 0:
        err = 'Remote error. Exit status: {0}. Error: {1}'.format(s, e.read())
        return False, err
    else:
        return True, o.read()