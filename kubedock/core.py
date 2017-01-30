
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import json
import socket
import time

import paramiko
import redis
from paramiko.ssh_exception import AuthenticationException, SSHException
from flask_sqlalchemy_fix import SQLAlchemy
from flask import current_app
from werkzeug.contrib.cache import RedisCache

from .login import LoginManager
from .settings import (REDIS_HOST, REDIS_PORT,
                       SSH_KEY_FILENAME,
                       SSE_KEEPALIVE_INTERVAL,
                       SSE_POLL_INTERVAL)


login_manager = LoginManager()

db = SQLAlchemy()
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


class ExclusiveLock(object):
    """Class for acquire and release named locks. It's implemented via
    Redis backend.

    """
    #: Prefix for all locks created by this class.
    lock_prefix = 'kd.exclusivelock.'

    def __init__(self, name, ttl=None):
        """Init Lock object.
        :param name: name of the lock
        :param ttl: number of seconds after acquiring when the lock must
        be automatically released.
        """
        self._redis_con = ConnectionPool().get_connection()
        self._lock = None
        self.name = self.lock_prefix + name
        self.ttl = ttl

    def lock(self, blocking=False):
        """Try to acquire the lock.
        If lock is already acquired, then immediately returns False
          if blocking=False (default). Wait lock release if blockging=True.
        If lock has been acquired, then returns True.
        :param blocking: optional flag specifying whether lock should be
          blocking or not
        """
        if self._lock is not None:
            return False
        self._lock = self._redis_con.lock(self.name, self.ttl)
        return self._lock.acquire(blocking=blocking)

    def release(self):
        """Release the lock."""
        if self._lock is None:
            return
        self._lock.release()

    @classmethod
    def is_acquired(cls, name):
        """Checks if the lock was already acquired and not yet released."""
        redis_con = ConnectionPool().get_connection()
        name = cls.lock_prefix + name
        lock = redis_con.lock(name, 1)
        res = False
        try:
            res = not lock.acquire(blocking=False)
        finally:
            try:
                lock.release()
            except redis.lock.LockError:
                # exception is raised in case of already released lock
                pass
        return res

    @classmethod
    def clean_locks(cls, pattern=None):
        """Removes all locks. Optionally may be specified prefix for lock's
        names.

        """
        redis_con = ConnectionPool().get_connection()
        if pattern:
            pattern = cls.lock_prefix + pattern + '*'
        else:
            pattern = cls.lock_prefix + '*'
        keys = list(redis_con.scan_iter(pattern))
        if keys:
            redis_con.delete(*keys)


class ExclusiveLockContextManager(object):

    def __init__(self, name, blocking=False, ttl=None):
        self.blocking = blocking
        self._lock = ExclusiveLock(name, ttl=ttl)

    def __enter__(self):
        return self._lock.lock(blocking=self.blocking)

    def __exit__(self, *_):
        self._lock.release()


class ServerSentEvents(object):

    def __init__(self):
        self._buff = []

    @staticmethod
    def _parse_message_text(text, encoding):
        """
        Generator to parse and decode data to be sent to SSE endpoint
        @param text: iterable -> list, tuple, set or string to be decoded
        @param encoding: string -> endocing to decode
        @return: generator
        """
        if isinstance(text, (list, tuple, set)):
            for item in text:
                if isinstance(item, bytes):
                    item = item.decode(encoding)
                for subitem in item.splitlines():
                    yield subitem
        else:
            if isinstance(text, bytes):
                text = text.decode(encoding)
            for item in text.splitlines():
                yield item

    def make_message(self, eid, event, text, encoding='utf-8'):
        """
        Makes message according to SSE standard
        @param eid: int -> message id
        @param event: string -> event type
        @param text: iterable -> message content
        @param encoding: string -> encoding to decode data
        @return: string -> decoded and formatted string data
        """
        self._buff.append("event:{0}\n".format(event))
        for text_item in self._parse_message_text(text, encoding):
            self._buff.append("data:{0}\n".format(text_item))
        if eid is not None:
            self._buff.append("id:{0}\n".format(eid))
        self._buff.append('\n')

    def __iter__(self):
        for item in self._buff:
            yield item
        self._buff = []


class EvtStream(object):
    key = 'SSEEVT'

    def __init__(self, conn, channel, last_id=None):
        self.conn = conn
        self.channel = channel
        self.pubsub = conn.pubsub()
        self.pubsub.subscribe(channel)
        self.last_id = last_id
        self.timeout = int(SSE_KEEPALIVE_INTERVAL / SSE_POLL_INTERVAL)
        self._time_is_out = self.timeout
        if self.last_id is not None:
            self.last_id = int(self.last_id)
        self.cache_key = ':'.join([self.key, channel])

    def __iter__(self):
        sse = ServerSentEvents()
        if self.last_id is not None:
            for key, value in sorted(
                ((int(k), v) for k, v in self.conn.hgetall(
                    self.cache_key).iteritems()), key=(lambda x: x[0])):
                if key <= self.last_id:
                    continue
                eid, event, data = json.loads(value)
                if not isinstance(data, basestring):
                    data = json.dumps(data)
                sse.make_message(eid, event, data)
                for msg in sse:
                    yield msg.encode('u8')
        else:
            yield ':\n\n'
        while True:
            message = self.pubsub.get_message()
            if message:
                if message['type'] == 'message':
                    eid, event, data = json.loads(message['data'])
                    if not isinstance(data, basestring):
                        data = json.dumps(data)
                    sse.make_message(eid, event, data)
                    for msg in sse:
                        yield msg.encode('u8')
            else:
                if not self._time_is_out:
                    self._time_is_out = self.timeout
                    yield ':\n\n'
                else:
                    self._time_is_out -= 1
            time.sleep(SSE_POLL_INTERVAL)


def ssh_connect(host, timeout=10):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    error_message = None
    try:
        ssh.connect(host, username='root', key_filename=SSH_KEY_FILENAME,
                    timeout=timeout)
    except (AuthenticationException, SSHException) as e:
        error_message =\
            '{0}.\nCheck hostname, check that user from which '.format(e) +\
            'Kuberdock runs (usually nginx) has ability to login as root on ' \
            'this node, and try again'
    except socket.timeout:
        error_message = 'Connection timeout({0} sec). '.format(timeout) +\
                        'Check hostname and try again'
    except socket.error as e:
        error_message =\
            '{0} Check hostname, your credentials, and try again'.format(e)
    except IOError as e:
        error_message =\
            'ssh_connect: cannot use SSH-key: {0}'.format(e)
    return ssh, error_message


class RemoteManager(object):
    """
    Set of helper functions for convenient work with remote hosts.
    """
    def __init__(self, host, timeout=10):
        self.raw_ssh, self.errors = ssh_connect(host, timeout)
        if self.errors:
            self.raw_ssh = None

    def close(self):
        self.raw_ssh.close()

    def exec_command(self, cmd):
        """
        Asynchronously execute command and return i, o, e  streams
        """
        return self.raw_ssh.exec_command(cmd)

    def fast_cmd(self, cmd):
        """
        Synchronously execute command
        :return: exit status and error string or data string if success
        """
        i, o, e = self.raw_ssh.exec_command(cmd)
        exit_status = o.channel.recv_exit_status()
        if exit_status == -1:
            return exit_status,\
                'No exit status, maybe connection is closed by remote server'
        if exit_status > 0:
            return exit_status, e.read()
        return exit_status, o.read()
