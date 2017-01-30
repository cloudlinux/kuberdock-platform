
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

import datetime
import fcntl
import json
import os
import random
import re
import socket
import string
import struct
import subprocess
import sys
import time
from collections import namedtuple
from contextlib import contextmanager
from functools import wraps
from itertools import chain
from json import JSONEncoder
from urlparse import urlsplit, urlunsplit, urljoin
from hashlib import md5

import bitmath
import ipaddress
import netifaces
import requests
import yaml
from flask import (current_app, request, jsonify, g, has_app_context, Response,
                   session, has_request_context)
from sqlalchemy.exc import SQLAlchemyError, InvalidRequestError
from werkzeug.wrappers import Response as ResponseBase

from .core import ssh_connect, db, ConnectionPool
from .exceptions import APIError, PermissionDenied, NoFreeIPs, NoSuitableNode
from .login import current_user, AnonymousUserMixin
from .rbac.models import Role
from .settings import (
    KUBE_MASTER_URL, KUBE_BASE_URL, KUBE_API_VERSION,
    ETCD_CALICO_HOST_CONFIG_KEY_PATH_TEMPLATE,
    ETCD_CALICO_HOST_KEY_PATH_TEMPLATE, ETCD_CALICO_URL
)
from .users.models import SessionData
from .constants import REDIS_KEYS


# Key in etcd to retrieve calico IP-in-IP tunnel address
# See:
#  https://github.com/projectcalico/calico-containers/blob/master/calicoctl/
#   calico_ctl/node.py
#  ->client.get_per_host_config(host_to_remove, "IpInIpTunnelAddr")
ETCD_KEY_CALICO_HOST_IP_TUNNEL_ADDRESS = 'IpInIpTunnelAddr'


class API_VERSIONS:
    v1 = 'v1'
    v2 = 'v2'
    acceptable = (v1, v2)
    default = v1


class UPDATE_STATUSES:
    """
    Possible upgrade statuses for both - upgrade scripts and node upgrades
    """
    started = 'started'
    master_applied = 'master applied'
    applied = 'applied'
    failed = 'failed'
    failed_downgrade = 'downgrade failed too'
    nodes_started = 'nodes started'
    nodes_failed = 'nodes failed'
    post_nodes_failed = 'post_nodes_hook failed'


class POD_STATUSES:
    """
    Possible pods statuses
    """
    running = 'running'
    stopped = 'stopped'
    pending = 'pending'
    succeeded = 'succeeded'
    failed = 'failed'
    unpaid = 'unpaid'  # TODO make this dbpod flag, not status
    preparing = 'preparing'
    stopping = 'stopping'
    deleting = 'deleting'
    deleted = 'deleted'


class NODE_STATUSES:
    """
    Possible node statuses
    """
    completed = 'completed'
    pending = 'pending'
    running = 'running'
    deletion = 'deletion'
    autoadded = 'autoadded'
    troubles = 'troubles'


def catch_error(action, trigger):
    """
    The decorator catches exception if any and runs corresponding actions
    :param action: string -> specifies action to be taken
    :param trigger: string -> sets exceptions to act upon
    """
    triggers = {
        'resources': (NoFreeIPs, NoSuitableNode)}

    def outer(f):
        @wraps(f)
        def inner(*args, **kw):
            try:
                return f(*args, **kw)
            except Exception, e:
                if trigger == 'all' or isinstance(
                        e, triggers.get(trigger, tuple())):
                    if action == 'notify':
                        err = re.sub(
                            r'(?:,\s?)?contact kuberdock administrator',
                            '', str(e), flags=re.IGNORECASE)
                        msg = 'User {0} got error: {1}'.format(
                            getattr(current_user, 'username', 'Unknown'), err)
                        send_event_to_role(
                            'notify:error', {'message': msg}, 'Admin')
                raise
        return inner
    return outer


def get_channel_key(conn, key, size=100):
    """
    Gets the last cache id for channel.
    If keys amount exceeds size truncate keys
    @param conn: object -> redis connection object
    @param key: string -> redis key for hash
    @param size: int -> key amount limit
    @return: int -> last key incremented by one
    """
    length = conn.hlen(key)
    if length == 0:
        return 1
    keys = sorted(conn.hkeys(key), key=int)
    if length >= size:
        for k in keys[:-(size - 1)]:
            conn.hdel(key, k)
    return int(keys[-1]) + 1


def get_throttle_pending_key(kd_pod_id, evt_str=None):
    """
    Generates part of redis key to use for throttling events
    :param kd_pod_id: KD pod id
    :param evt_str: string to hash that represent some unique event
    :return: generated key
    :rtype: str
    """
    res = 'schedule_{}_'.format(kd_pod_id)
    if evt_str:
        res += md5(evt_str).hexdigest()
    return res


def throttle_evt(key, seconds, redis=None):
    """
    Redis-based throttler.
    Use as follows:
            if not throttle_evt(key, 100):
                do_something()
    :param key: Pre-Composed key for redis
    :param seconds: seconds to throttle_evt - will be a redis key TTL
    :param redis: optional redis connection to use
    :return: flag whether execution should be skipped or no
    :rtype: bool
    """
    key = REDIS_KEYS.THROTTLE_PREFIX + key
    if redis is None:
        redis = ConnectionPool.get_connection()
    if redis.exists(key):
        return True
    else:
        redis.set(key, str(datetime.datetime.now()), ex=seconds)
        return False


def send_event_to_user(event_name, data, user_id, to_file=None,
                       prefix='SSEEVT'):
    """
    Selects all given user sessions and sends list to send_event
    """
    sessions = [i.id for i in SessionData.query.filter(
        (SessionData.user_id == user_id) |
        (SessionData.impersonated_id == user_id))]
    send_event(event_name, data, to_file, sessions, prefix)


def send_event_to_role(event_name, data, role, to_file=None, prefix='SSEEVT'):
    """
    Selects all given role user sessions and sends list to send_event
    """
    if isinstance(role, basestring):
        role = db.session.query(Role.id).filter(Role.rolename == role).scalar()
    sessions = [i.id for i in SessionData.query.filter_by(role_id=role)]
    send_event(event_name, data, to_file, sessions, prefix)


def resolve_channels(channels, role='Admin'):
    """
    Tries to produce a valid channels list
    @param channels: string, list, tuple or None
    @param role: string -> role to map channels to when channels are missing
    @return: list
    """
    if channels is None:
        if has_request_context():
            channels = getattr(session, 'sid', None)
        if channels is None:
            rid = Role.query.filter_by(rolename=role).first()
            if rid is None:
                return []
            return [i.id for i in SessionData.query.filter_by(role_id=rid.id)]
    if not isinstance(channels, (tuple, list)):
        return [channels]
    return channels


def send_event(event_name, data, to_file=None, channels=None, prefix='SSEEVT'):
    """
    Sends event via pubsub to all subscribers and cache it to be rolled back
    if missed
    @param event_name: string -> event name
    @param data: dict -> data to be sent
    @param to_file: file handle object -> file object to output logs
    @param channels: list -> target identifiers for event to be sent to
    @param prefix: string -> redis key prefix to store channel cache
    """
    channels = resolve_channels(channels)
    conn = ConnectionPool.get_connection()
    for channel in channels:
        key = ':'.join([prefix, channel])
        channel_key = get_channel_key(conn, key)
        message = json.dumps([channel_key, event_name, data])
        conn.hset(key, channel_key, message)
        conn.publish(channel, message)
    if to_file is not None:
        try:
            to_file.write(data)
            to_file.write('\n')
            to_file.flush()
        except Exception as e:
            print 'Error writing to log file', e.__repr__()


def send_logs(node, data, to_file=None, channels=None):
    channels = resolve_channels(channels)
    conn = ConnectionPool.get_connection()
    msg = json.dumps([None, 'node:installLog', {'id': node, 'data': data}])
    for channel in channels:
        conn.publish(channel, msg)
    if to_file is not None:
        try:
            to_file.write(data)
            to_file.write('\n')
            to_file.flush()
        except Exception as e:
            print 'Error writing to log file', e.__repr__()


def update_dict(src, diff):
    for key, value in diff.iteritems():
        if type(value) is dict and key in src:
            update_dict(src[key], value)
        else:
            src[key] = value


def get_api_url(*args, **kwargs):
    """
    Returns URL
    :param args:
    :param kwargs:
        namespace - namespace
        api_version - overrides default api version
        watch - True if you need append ?watch=true
        base_url - override the base url specified in KUBE_MASTER_URL. It
        should begin with a leading slash in order to work properly. For
        example given KUBE_MASTER_URL = http://localhost:1/api/ and
        base_url = /apis/kuberdock.com the final URL will be
        http://localhost:1/apis/kuberdock.com/...
    :return: string
    """
    schema, host, url, query, fragment = list(urlsplit(KUBE_MASTER_URL))

    if kwargs.get('watch'):
        schema, query = 'ws', 'watch=true'

    url_parts = [
        kwargs.get('base_url', KUBE_BASE_URL),
        kwargs.get('api_version', KUBE_API_VERSION),
    ]

    namespace = kwargs.get('namespace', 'default')
    if namespace:
        url_parts += ['namespaces', namespace]

    url = urljoin(url, '/'.join(url_parts + [str(a) for a in args]))

    return urlunsplit([schema, host, url, query, fragment])


def k8s_json_object_hook(obj):
    """Convert things like datetime to native python types.

    Example:
        response = requests.get('https://localhost:8080/api/v1/pods')
        pods = response.json(object_hook=k8s_json_object_hook)
    """
    for key, value in obj.iteritems():
        if isinstance(value, basestring):
            dt = parse_datetime_str(value)
            if dt is not None:
                obj[key] = dt
    return obj


class atomic(object):
    """Wrap code in transaction. Can be used as decorator or context manager.

    If the block of code is successfully completed, the transaction is
    committed.
    If there is an exception, the transaction is rolled back.
    Saves you from repeating `try-except-rollback` and adds `commit=True/False`
    parameter to decorated functions.
    You can find some usage examples in `.tests.utils.TestAtomic` or
    `.kapi.users`.

    :param api_error: Exception instance or a callable that accepts
        (exc_type, exc_value, traceback) and returns an exception.
        If not None, will be raised instead of any exception that is not an
        APIError subclass.
    :param nested: set it to `False` if you want this wrapper to use your
        current transaction instead of creating a new nested one.
        In case of a decorator, this behavior can be overridden by passing
        `commit=True/False` into decorated function.
    """

    class UnexpectedCommit(SQLAlchemyError):
        """Raised before commit inside atomic block happens."""

    class UnexpectedRollback(SQLAlchemyError):
        """Raised, if rollback inside atomic block happens."""

    def __init__(self, api_error=None, nested=True):
        self.api_error = api_error
        self.nested = nested
        self.nested_override = None

    def __call__(self, func):
        @wraps(func)
        def decorated(*args, **kwargs):
            if 'commit' in kwargs:
                self.nested_override = not kwargs.pop('commit')
            with self:
                return func(*args, **kwargs)

        return decorated

    def __enter__(self):
        # need to do only once per request
        if getattr(g, 'atomics', None) is None:
            g.atomics = []

        # need to do every __enter__()
        nested = self.nested if self.nested_override is None else \
            self.nested_override
        g.atomics.append(db.session.begin_nested() if nested else
                         db.session.registry().transaction)
        self.nested_override = None

    def _rollback(self, transaction, exc_type, exc_value, traceback):
        if not isinstance(exc_value, self.UnexpectedRollback):
            transaction.rollback()
        if callable(self.api_error):
            api_error = self.api_error(exc_type, exc_value, traceback)
        else:
            api_error = self.api_error
        if api_error and not isinstance(exc_value, APIError):
            current_app.logger.warn('Exception inside atomic block',
                                    exc_info=(exc_type, exc_value, traceback))
            raise api_error

    def __exit__(self, exc_type, exc_value, traceback):
        transaction = g.atomics.pop()
        if exc_value is not None:
            self._rollback(transaction, exc_type, exc_value, traceback)
        else:
            try:
                transaction.commit()
            except Exception:
                self._rollback(transaction, *sys.exc_info())
                raise

    @classmethod
    def _unexpectedly_closed(cls, session, rolled_back=None):
        msg = ("Prevented attempt to close main transaction inside `atomic` "
               "block.\n"
               "This error may happen if you called `db.session.{0}()`, "
               "but didn't call `db.session.begin_nested()`.")
        if has_app_context() and getattr(g, 'atomics', None):
            # check that the deepest transaction is ok
            transaction = g.atomics[-1]
            if rolled_back is None and session.transaction == transaction:
                raise cls.UnexpectedCommit(msg.format('commit'))
            elif rolled_back == transaction:
                raise cls.UnexpectedRollback(msg.format('rollback'))

    @classmethod
    def register(cls):
        db.event.listen(db.session, 'before_commit', cls._unexpectedly_closed)
        db.event.listen(db.session, 'after_soft_rollback',
                        cls._unexpectedly_closed)

    @classmethod
    def unregister(cls):
        try:
            db.event.remove(db.session, 'before_commit',
                            cls._unexpectedly_closed)
            db.event.remove(db.session, 'after_soft_rollback',
                            cls._unexpectedly_closed)
        except InvalidRequestError:  # ok, it is not registered
            pass


atomic.register()


def hostname_to_ip(name):
    """
    Converts hostname to IP address
    :param name: string -> hostname
    :return: string -> IP address or None
    """
    try:
        return socket.gethostbyname(name)
    except socket.gaierror:
        pass


# TODO: remove after handle_aws_node
def compose_dnat(*params):
    """
    Composes iptables DNAT rule
    :param params: array of positional params
    :return: string -> iptables rule
    """
    IPTABLES = ('iptables -t nat -{0} PREROUTING -i {1} -p {2} '
                '-d {3} --dport {4} -j DNAT --to-destination {5}:{6}')
    return IPTABLES.format(*params)


def get_available_port(host):
    """
    Generates random port in loop and tries to connect to specified host
    if connections failed consider port is free and return it
    We do not take into account filtered ports
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        port = random.randint(10000, 65535)
        rv = sock.connect_ex((host, port))
        if rv != 0:
            return port


def get_instance_data(conn, name):
    """
    Gets amazon instance by internal DNS name and return instance id and
    some misc info
    :param conn: object -> boto ec2 connection object
    :param name: string -> instance internal DNS name
    :return: dict -> dict of arrays: instances, security groups,
    subnets and VPCs
    """
    instances = []
    sg = set()
    sn = set()
    vpc = set()
    filters = {'private_dns_name': name}
    for r in conn.get_all_reservations(filters=filters):
        for i in r.instances:
            instances.append(i.id)
            for group in i.groups:
                sg.add(group.id)
            sn.add(i.subnet_id)
            vpc.add(i.vpc_id)
    return {'instances': instances, 'sg': list(sg), 'sn': list(sn),
            'vpc': list(vpc)}


def get_security_group(conn, name='kuberdock-elb-default'):
    """
    Gets and returns aws security group id by name if any
    :param conn: object -> boto ec2 connection object
    :param name: string -> security group name to search for
    :return: list -> list of security groups IDs
    """
    sgs = conn.get_all_security_groups()
    for sg in sgs:
        if name == sg.name and sg.vpc_id is not None:
            return [sg.id]
    return []


def create_security_group(conn, vpc_id, name='kuberdock-elb-default'):
    """
    Creates security group in given VPC
    :param conn: object -> boto ec2 connection object
    :param vpc_id: string -> VPC ID security group to belong to
    :param name: string -> security group name to search for
    :return: list -> list of security groups IDs
    """
    desc = 'default kuberdock ELB security group'
    sg = conn.create_security_group(name, desc, vpc_id=vpc_id)
    rv = sg.authorize('tcp', 0, 65535, '0.0.0.0/0')
    if rv:
        return [sg.id]
    return []


# TODO: remove after handle_aws_node
def get_current_dnat(conn):
    """
    Gets all node iptables DNAT rules. Get host port, pod IP,
    pod port for a rule
    :param conn: object -> ssh connection object
    :return: list -> list of namedtuples of data (host_port, pod_ip,
    pod_port)
    """
    inp, out, err = conn.exec_command("iptables -t nat -L PREROUTING -n")
    rules = []
    patt = re.compile(r'/\*.*?\*/')
    NetData = namedtuple('NetData', 'host_port pod_ip pod_port')
    for rule in out.read().splitlines():
        if not rule.startswith('DNAT'):
            continue
        rules.append(
            NetData._make(
                map((lambda x: int(x) if x.isdigit() else x),
                    chain(*[i.split(':')[1:]
                            for i in patt.sub('', rule).split()[-2:]]))))
    return rules


def get_load_balancer(conn, service_name):
    """
    We name our load balancers after service name.
    A load balancer may have more than one listener entity,
    so we get load balancer by name and then get its
    listeners
    :param conn: object -> boto ec2 connection object
    :param service_name: string -> service name
    :return: object -> found listener object or None
    """
    elbs = conn.get_all_load_balancers()
    filtered = [elb for elb in elbs if elb.name == service_name]
    if filtered:
        return filtered[0]


def unregistered_pod_warning(pod_id):
    current_app.logger.warn(
        'Pod with id {0} is not registered in Kuberdock '
        'database, but was found in kubernetes.'.format(pod_id))


def pod_without_id_warning(name, namespace):
    current_app.logger.warn(
        'Pod with metadata.name {0} and metadata.namespace {1} have no '
        'kuberdock-pod-uid. Maybe someone created it using kubernetes, '
        'bypass kuberdock.'.format(name, namespace))


class JSONDefaultEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


def run_ssh_command(host, command):
    ssh, error_message = ssh_connect(host)
    if error_message:
        raise APIError(error_message)
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        message = stdout.read()
    else:
        message = stderr.read()
    ssh.close()
    return exit_status, message


def all_request_params():
    # pretty ugly. Wants refactoring
    params = {}
    data = request.args.to_dict()
    if data is not None:
        params.update(data)
    data = request.json
    if data is not None:
        params.update(data)
    data = request.form.to_dict()
    if data is not None:
        params.update(data)
    params.pop('token', None)  # remove auth token from params if exists
    params.pop('token2', None)
    return params


class KubeUtils(object):
    @staticmethod
    def get_current_user():
        if hasattr(current_user, 'username'):
            return current_user
        else:
            return getattr(g, 'user', AnonymousUserMixin())

    @classmethod
    def jsonwrap(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rv = func(*args, **kwargs)
            if isinstance(rv, (Response, ResponseBase)):
                return rv
            response = {'status': 'OK'}
            if rv is not None:
                response['data'] = rv
            return jsonify(response)

        return wrapper

    @classmethod
    def pod_start_permissions(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = cls.get_current_user()
            params = cls._get_params()
            if ('command' in params and params['command'] in ['start'] or
                    params) and user.suspended is True:
                raise PermissionDenied(
                    'Permission denied. Your account is suspended. '
                    'Your package has expired. Please upgrade it.')
            return func(*args, **kwargs)

        return wrapper

    @staticmethod
    def _get_params():
        return all_request_params()


def register_api(bp, view, endpoint, url, pk='id', pk_type='string', **kwargs):
    view_func = view.as_view(endpoint)
    bp.add_url_rule(url, view_func=view_func, methods=['GET'],
                    defaults={pk: None}, **kwargs)
    bp.add_url_rule(url, view_func=view_func, methods=['POST'], **kwargs)
    bp.add_url_rule('{0}<{1}:{2}>'.format(url, pk_type, pk),
                    view_func=view_func,
                    methods=['GET', 'PUT', 'PATCH', 'DELETE'], **kwargs)


def from_binunit(value, unit='Byte', precision=None, rtype=None):
    """Convert binary unit value to numeric value

    :param value: value to convert
    :type value: str
    :param unit: destination unit ('GiB', 'MiB', 'KiB' or any bitmath unit)
    :type unit: str
    :param precision: round precision
    :type precision: int
    :param rtype: return type (default: int if unit is 'Byte' or
    precision <= 0, float otherwize)
    :type rtype: float, int or any type that can handle float as argument
    :returns: converted value
    :rtype: float, int or rtype defined
    :raises: ValueError, TypeError

    :Examples:
    >>> from_binunit('1017368Ki')
    1041784832
    >>> from_binunit('1017368Ki', 'GiB', 2)
    0.97
    >>> from_binunit('1017368Ki', 'GiB', 0)
    1
    >>> from_binunit('1017368Ki', 'MiB')
    993.5234375
    >>> from_binunit('1017368Ki', 'MiB', 0)
    994
    >>> from_binunit('1017368Ki', 'MiB', rtype=int)
    993
    >>> from_binunit('1017368Ki', 'MiB', 0, float)
    994.0
    >>> from_binunit('1017368Ki', 'MiB', rtype=lambda x: float(int(x)))
    993.0
    """

    if unit.endswith('i'):
        unit += 'B'
    if isinstance(value, basestring):
        if isinstance(value, unicode):
            value = str(value)
        if value.endswith('i'):
            value += 'B'
        result = bitmath.parse_string(value)
        result = getattr(result, unit).value
    else:
        result = float(value) / getattr(bitmath, unit)(1).bytes
    if precision is not None:
        result = round(result, precision)
    if rtype is None:
        if unit == 'Byte' or (precision is not None and precision <= 0):
            rtype = int
        else:
            rtype = float
    return rtype(result)


def parse_datetime_str(instr):
    """Converts given string to datetime object.
    Incoming string is expected to be in subset of ISO 8601 format.
    Understands the following dates:
        "2000-01-20"
        "2000-01-20 12:34:56"
        "2000-01-20T12:34:56"
        "2000-01-20T12:34:56Z"
    """
    DATE_FMT = '%Y-%m-%d'
    TIME_FMT = '%H:%M:%S'
    formats = [DATE_FMT,
               DATE_FMT + ' ' + TIME_FMT,
               DATE_FMT + 'T' + TIME_FMT,
               DATE_FMT + 'T' + TIME_FMT + 'Z']
    for format in formats:
        try:
            return datetime.datetime.strptime(instr, format)
        except ValueError:
            pass


LOCALTIME = '/etc/localtime'
ZONEINFO = '/usr/share/zoneinfo'


def get_timezone(default_tz=None):
    if os.path.islink(LOCALTIME):
        localtime = os.path.realpath(LOCALTIME)
        if os.path.commonprefix((localtime, ZONEINFO)) == ZONEINFO:
            return os.path.relpath(localtime, ZONEINFO)
    if default_tz:
        return default_tz
    raise OSError('Time zone cannot be determined')


def from_siunit(value):
    """Convert SI unit value to float

    :param value: value to convert
    :type value: str
    :returns: converted value
    :rtype: float
    :raises: ValueError

    :Examples:
    >>> from_siunit('4')
    4.0
    >>> from_siunit('2200m')
    2.2
    """

    if value.endswith('m'):
        ratio = 1000
        value = value[:-1]
    else:
        ratio = 1

    new_value = float(value) / ratio
    return new_value


def get_version(package):
    """
    Get RPM package version
    :param package: string -> RPM package name
    :param patt: object -> compiled regexp
    :return: string -> version of the given package or None if missing
    """
    try:
        rv = subprocess.check_output(
            ['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', package]
        )
        return rv
    except (subprocess.CalledProcessError, AttributeError):
        return 'unknown'


def randstr(length=8, symbols=string.ascii_letters + string.digits,
            secure=False):
    """
    Generate random string with secure randomness generator if secure is True
    :param length: length of string
    :param symbols: symbols for choice()
    :param secure: whether to use secure SystemRandom generator
    :return: generated string
    """
    rnd = random.SystemRandom() if secure else random.Random()
    return ''.join(rnd.choice(symbols) for _ in range(length))


def retry(f, retry_pause, max_retries, exc=None, *f_args, **f_kwargs):
    """
    Retries the given function call until it returns non-empty value
    or max_retries exceeds.

    :param f: a function to retry
    :param retry_pause: pause between retries (seconds)
    :param max_retries: max retries num.
    :param exc: exception obj to throw after max retries.
    :return:
    """
    for _ in range(max_retries):
        ret_val = f(*f_args, **f_kwargs)
        if ret_val:
            return ret_val
        time.sleep(retry_pause)
    if exc:
        raise exc


def retry_with_catch(f, max_tries=1, retry_pause=0, exc_types=(Exception,),
                     callback_on_error=None, args=(), kwargs=None):
    """Retries the given function call on errors. If max_retries reached,
    last error will be raised.

    ATTENTION: the signature is different from `retry`.

    :param f: a function to retry.
    :param max_tries: max tries num.
    :param retry_pause: pause between retries (seconds).
    :param exc_types: types of handled exceptions.
    :param callback_on_error: callback that will be called on each
        handled error. Exception instance will be passed as an argument.
    :param args: args of function
    :param kwargs: kwargs of function
    :return:
    """
    if kwargs is None:
        kwargs = {}
    for _ in range(max_tries - 1):
        try:
            return f(*args, **kwargs)
        except exc_types as e:
            if callback_on_error:
                callback_on_error(e)
            time.sleep(retry_pause)
    try:
        return f(*args, **kwargs)
    except exc_types as e:
        if callback_on_error:
            callback_on_error(e)
        raise e


def ip2int(ip):
    return int(ipaddress.IPv4Address(ip))


def int2ip(number):
    return unicode(ipaddress.IPv4Address(number))


def send_pod_status_update(pod_status, db_pod, event_type):
    """Sends pod status change to frontend.
    Must be executed in application context.
    """
    key_ = 'pod_state_' + db_pod.id

    redis = ConnectionPool.get_connection()
    prev_state = redis.get(key_)
    user_id = db_pod.owner_id
    current = pod_status
    deleted = event_type == 'DELETED'
    if prev_state != current or deleted:
        redis.set(key_, 'DELETED' if deleted else current)
        event = (
            'pod:delete' if db_pod.status in ('deleting', 'deleted') else
            'pod:change'
        )
        send_event_to_role(event, {'id': db_pod.id}, 'Admin')
        send_event_to_user(event, {'id': db_pod.id}, user_id)


class NestedDictUtils(object):
    """Set of utils for working with dictionaries."""

    @classmethod
    def get(cls, d, path):
        """Get nested field from dict suppressing KeyError.
        E.g.: get(d, 'persistentDisk.pdName')
        """
        if not path:
            raise ValueError
        parts = path.split('.')
        with cls._check_nested_types_context():
            for p in parts:
                d = d.get(p)
                if d is None:
                    return None
            return d

    @classmethod
    def set(cls, d, path, value):
        """Set nested dict field creating nested dicts if necessary.
        E.g.: set(d, 'persistentDisk.pdName', 'nginx_volume')
        """
        if not path:
            raise ValueError
        parts = path.split('.')
        with cls._check_nested_types_context():
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[parts[-1]] = value

    @classmethod
    def delete(cls, d, path, remove_empty_keys=False):
        """Delete nested field from dict suppressing KeyError.
        E.g.: delete(d, 'persistentDisk.pdName')
        """
        if not path:
            raise ValueError
        parts = path.split('.')
        nodes = []
        with cls._check_nested_types_context():
            for p in parts:
                parent = d
                d = d.get(p)
                if d is None:
                    return
                nodes.append(cls._dict_node(p, d, parent))
            if nodes:
                n = nodes.pop()
                del n.parent[n.key]
                if remove_empty_keys:
                    for n in reversed(nodes):
                        if not n.value:
                            del n.parent[n.key]

    _dict_node = namedtuple('_dict_node', ('key', 'value', 'parent'))

    @classmethod
    @contextmanager
    def _check_nested_types_context(cls):
        try:
            yield
        except (AttributeError, TypeError):
            raise cls.StructureError

    class StructureError(Exception):
        """Raised if expected nested dict is not dict,
        e.g. `d = {'x': {'y': 2}}` and user tries to get path `x.y.z` --
        in this case expected that `y` is dict, but it is not.
        """
        message = 'All nested dicts must be instance of dict'

nested_dict_utils = NestedDictUtils


def domainize(input_str):
    """
    Normalize string to DNS-valid character sequence

    :param input_str: input line to be normalized
    :type input_str: str | unicode
    :return: DNS valid line to be used as part of Domain Name
    :rtype: str
    """
    str_ = input_str.lower()
    # remove any symbols except ASCII digits and lowercase letters
    str_ = re.sub('[^0-9a-z]', '', str_)
    return str_


def get_node_token():
    try:
        with open('/etc/kubernetes/configfile_for_nodes') as node_configfile:
            node_configfile_raw = node_configfile.read()
        token = yaml.load(node_configfile_raw)['users'][0]['user']['token']
        return token
    except (IOError, yaml.YAMLError, KeyError, IndexError):
        return None


# TODO possibly not needed anymore
def get_ip_address(ifname):
    # http://stackoverflow.com/a/24196955
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])
    except IOError:
        return None


class Etcd(object):

    RequestException = requests.RequestException

    def __init__(self, url, verify=None, cert=None):
        self.verify = verify
        self.cert = cert
        self.url = url

    def _url(self, key):
        if key is not None:
            url = '/'.join([self.url, key])
        else:
            url = self.url
        return url

    def _make_request(self, method, key, *args, **kwargs):
        url = self._url(key)
        if self.verify is not None:
            kwargs['verify'] = self.verify
        if self.cert:
            kwargs['cert'] = self.cert
        response = method(url, *args, **kwargs)
        response.raise_for_status()
        return response.json()

    def exists(self, key):
        try:
            self._make_request(requests.get, key)
        except requests.exceptions.HTTPError:
            return False
        return True

    def delete(self, key):
        return self._make_request(requests.delete, key)

    def put(self, key, value=None, asjson=True):
        if asjson:
            value = json.dumps(value)
        data = None if value is None else {'value': value}
        return self._make_request(requests.put, key, data=data)

    def get(self, key=None, recursive=False):
        response = self._make_request(requests.get, key,
                                      params={'recursive': recursive})
        return response


def get_hostname():
    """
    Get Static Hostname
    :return: String representation of the hostname.
    """
    try:
        hostname = subprocess.check_output(['hostnamectl', '--static'])
        return hostname.strip()
    except (OSError, subprocess.CalledProcessError):
        # If something goes wrong
        # return socket.gethostname instead of just erroring.
        return socket.gethostname()


def get_current_host_ips():
    """
    :return: list of all IPv4 addresses on this host including loopback
    """
    all_ips = []
    for ifaceName in netifaces.interfaces():
        for addr_rec in netifaces.ifaddresses(ifaceName).setdefault(
                netifaces.AF_INET, [None]):
            if addr_rec is not None and 'addr' in addr_rec:
                all_ips.append(addr_rec['addr'])
    return all_ips


def get_calico_ip_tunnel_address(hostname=None):
    """Returns current address of ipip tunnel of calico node.
    :param hostname: name of host, if not defined, then will be used current
        host name.
    :return: string with IP address. If address retrieving will fail, then
        return None
    """
    if not hostname:
        hostname = get_hostname()
    url = ETCD_CALICO_HOST_CONFIG_KEY_PATH_TEMPLATE.format(
        hostname=hostname) + '/' + ETCD_KEY_CALICO_HOST_IP_TUNNEL_ADDRESS
    try:
        result = Etcd(url).get()
    except requests.exceptions.HTTPError:
        return None
    return result[u'node'][u'value']


def get_current_calico_hosts():
    """
    Return all calico hosts currently present in etcd as list of strings
    :return: list, error_str
    """
    res = []
    try:
        resp = Etcd(ETCD_CALICO_URL + '/host/').get()
        for host in resp[u'node'][u'nodes']:
            if host[u'dir']:
                hostname = host[u'key'].rsplit(u'/', 1)[-1]
                res.append(hostname)
    except (requests.exceptions.HTTPError, KeyError):
        return None, "Can't get list of calico hosts"
    return res, None


def get_calico_host_bird_ip(hostname):
    try:
        resp = Etcd(
            ETCD_CALICO_HOST_KEY_PATH_TEMPLATE.format(hostname=hostname) +
            '/bird_ip').get()
        return resp[u'node'][u'value'], None
    except (requests.exceptions.HTTPError, KeyError):
        return None, "Can't get calico host bird ip"


def find_calico_host_by_ip(bird_ip):
    all_hosts, err = get_current_calico_hosts()
    if err:
        return None, err

    for host in all_hosts:
        host_bird_ip, err = get_calico_host_bird_ip(host)
        if not host_bird_ip:
            return None, err
        if host_bird_ip == bird_ip:
            return host, None
    return None, None


@contextmanager
def session_scope(session):
    """
    Provide a transactional scope around a series of operations.
    (Taken from http://docs.sqlalchemy.org/en/latest/orm/session_basics.html)
    WARNING: this implementation doesn't create new session, but reuses
    existing like:
        with session_scope(db.session):
            ...
    """
    try:
        yield
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def _find_calico_host(nodes, ip):
    for node in nodes:
        for sub_node in node['nodes']:
            if sub_node.get('value') == ip:
                return node['key'].split('/')[-1]


def find_remote_host_tunl_addr(ip):
    calico_host, err = find_calico_host_by_ip(ip)

    if err:
        return None, err

    if not calico_host:
        # Calico node with this IP is not added yet
        return None, None

    remote_host_tunl_addr = get_calico_ip_tunnel_address(calico_host)

    if not remote_host_tunl_addr:
        # This is possibly a case when calico ipip tunnel is not ready yet
        return None, None

    return remote_host_tunl_addr, None


class InvalidAPIVersion(APIError):
    def __init__(self, apiVersion=None,
                 acceptableVersions=API_VERSIONS.acceptable):
        if apiVersion is None:
            apiVersion = g.get('api_version')
        super(InvalidAPIVersion, self).__init__(details={
            'apiVersion': apiVersion,
            'acceptableVersions': acceptableVersions,
        })

    @property
    def message(self):
        apiVersion = self.details.get('apiVersion')
        acceptableVersions = ', '.join(self.details.get('acceptableVersions'))
        return (
            'Invalid api version: {apiVersion}. Acceptable versions are: '
            '{acceptableVersions}.'.format(
                apiVersion=apiVersion, acceptableVersions=acceptableVersions))


class check_api_version(object):
    """Check that api version in request is one of `acceptable_versions`.

    Can be used as decorator, callback (use #check method), or coerced to
    boolean.
    """
    def __init__(self, acceptable_versions):
        self.acceptable_versions = acceptable_versions

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wraps(func)(wrapper)

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def __nonzero__(self):
        return g.api_version in self.acceptable_versions

    def check(self):
        if not self:
            raise InvalidAPIVersion(
                acceptableVersions=self.acceptable_versions)


def get_node_interface(data, node_ip):
    ip = ipaddress.ip_address(unicode(node_ip))
    patt = re.compile(r'(?P<iface>\w+)\s+inet\s+(?P<ip>[0-9\/\.]+)')
    for line in data.splitlines():
        m = patt.search(line)
        if m is None:
            continue
        iface = ipaddress.ip_interface(unicode(m.group('ip')))
        if ip == iface.ip:
            return m.group('iface')
