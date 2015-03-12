from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.influxdb import InfluxDB
from flask.ext.login import LoginManager
from flask import current_app
from sse import Sse
import redis
import json
import paramiko
import requests
import gevent
from paramiko import ssh_exception
import socket
from .settings import DEBUG, NODE_SSH_AUTH, NODE_INET_IFACE
from .settings import KUBE_MASTER_URL
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


def process_event(kub_event):
    # TODO handle pods migrations
    try:
        kub_event = json.loads(kub_event.strip())
    except ValueError:
        print 'Wrong event data in process_event: "{0}"'.format(kub_event)
        return True
    public_ip = kub_event['object']['labels'].get('kuberdock-public-ip')
    if (not public_ip) or (kub_event['type'] == "ADDED"):
        return False
    pod_ip = kub_event['object']['currentState'].get('podIP')
    if not pod_ip:
        return True
    conts = kub_event['object']['desiredState']['manifest']['containers']

    ARPING = 'arping -I {0} -A {1} -c 10 -w 1'
    IP_ADDR = 'ip addr {0} {1}/32 dev {2}'
    IPTABLES = 'iptables -t nat -{0} PREROUTING ' \
               '-i {1} ' \
               '-p tcp -d {2} ' \
               '--dport {3} -j DNAT ' \
               '--to-destination {4}:{3}'
    if kub_event['type'] == "MODIFIED":
        cmd = 'add'
    elif kub_event['type'] == "DELETED":
        cmd = 'del'
    else:
        print 'Skip event type %s' % kub_event['type']
        return False
    ssh, errors = ssh_connect(kub_event['object']['currentState']['host'])
    ssh.exec_command(IP_ADDR.format(cmd, public_ip, NODE_INET_IFACE))
    if cmd == 'add':
        ssh.exec_command(ARPING.format(NODE_INET_IFACE, public_ip))
    for container in conts:
        for port_spec in container['ports']:
            if cmd == 'add':
                i, o, e = ssh.exec_command(
                    IPTABLES.format('C', NODE_INET_IFACE, public_ip,
                                    port_spec['containerPort'],
                                    pod_ip))
                exit_status = o.channel.recv_exit_status()
                if exit_status != 0:
                    ssh.exec_command(
                        IPTABLES.format('I', NODE_INET_IFACE, public_ip,
                                        port_spec['containerPort'],
                                        pod_ip))
            else:
                ssh.exec_command(
                    IPTABLES.format('D', NODE_INET_IFACE, public_ip,
                                    port_spec['containerPort'],
                                    pod_ip))
    ssh.close()
    return False


def listen_kub_events():
    while True:
        r = requests.get(KUBE_MASTER_URL + '/watch/pods', stream=True)
        # TODO if listen endpoinds must skip 3 events
        # (1 last +  2 * kubernetes endpoints)
        # maybe more if we have more services
        while not r.raw.closed:
            content_length = r.raw.readline()
            if content_length not in ('0', ''):
                # TODO due to watch bug:
                needs_reconnect = process_event(r.raw.readline())
                if needs_reconnect:
                    r.raw.close()
                    gevent.sleep(0.2)
                    break
                r.raw.readline()
        # print 'RECONNECT(Listen pods events)'