import datetime
import json
import os
import random
import re
import socket
import string
import subprocess
import sys
import time
from collections import namedtuple
from functools import wraps
from itertools import chain
from json import JSONEncoder
from traceback import format_exception
from urlparse import urlsplit, urlunsplit, urljoin

import bitmath
import boto.ec2
import boto.ec2.elb
import nginx
from flask import (current_app, request, jsonify, g, has_app_context, Response,
                   session, has_request_context)
from sqlalchemy.exc import SQLAlchemyError, InvalidRequestError

from .core import ssh_connect, db, ConnectionPool
from .exceptions import APIError, PermissionDenied, NoFreeIPs, NoSuitableNode
from .login import current_user
from .pods import Pod
from .rbac.models import Role
from .settings import KUBE_MASTER_URL, KUBE_API_VERSION
from .settings import NODE_TOBIND_EXTERNAL_IPS
from .users.models import SessionData


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


def send_event_to_user(event_name, data, user_id, to_file=None,
                       prefix='SSEEVT'):
    """
    Selects all given user sessions and sends list to send_event
    """
    sessions = [i.id for i in SessionData.query.filter_by(user_id=user_id)]
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

    if 'base_url' in kwargs:
        url = kwargs['base_url'] + '/'

    url_parts = [kwargs.get('api_version', KUBE_API_VERSION)]

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

    :param api_error: if not None, will be raised instead of any exception
        that is not an APIError subclass.
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
        if self.api_error and not isinstance(exc_value, APIError):
            current_app.logger.warn(
                ''.join(format_exception(exc_type, exc_value, traceback)))
            raise self.api_error

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


def register_elb_name(service, name):
    """
    Saves received from ELB DNS name in the DB
    :param name: string -> DNS name to be saved
    """
    item = db.session.query(Pod).filter(
        (Pod.status != 'deleted') & (
            Pod.config.like('%' + service + '%'))).first()
    if item is None:
        return
    data = json.loads(item.config)
    data['public_aws'] = name
    item.config = json.dumps(data)
    db.session.commit()


def get_pod_owner_id(service):
    """
    Returns pod owner from db
    :param service: string -> service name
    :return: integer
    """
    item = db.session.query(Pod).filter(
        (Pod.status != 'deleted') & (
            Pod.config.like('%' + service + '%'))).first()
    if item is None:
        return
    return item.owner_id


# TODO: need to be moved to network plugin
def handle_aws_node(ssh, service, host, cmd, pod_ip, ports, app):
    try:
        from .settings import REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    except ImportError:
        return

    conn = boto.ec2.connect_to_region(
        REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    elbconn = boto.ec2.elb.connect_to_region(
        REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    data = get_instance_data(conn, host)
    private_ip = hostname_to_ip(host)
    elb = get_load_balancer(elbconn, service)
    elb_rules = []
    if elb:
        elb_rules.extend(elb.listeners)
    rules = get_current_dnat(ssh)

    if cmd == 'add':
        listeners = []
        for port_spec in ports:
            if not port_spec['name'].endswith('-public'):
                continue
            container_port = port_spec['targetPort']
            public_port = port_spec.get('port', container_port)
            protocol = port_spec.get('protocol', 'tcp')

            match = [i for i in rules
                     if (i.pod_ip, i.pod_port) == (pod_ip, container_port)]

            port = None
            if not match:
                port = get_available_port(host)
                if port is None:
                    return False

                new_rule = compose_dnat('I', NODE_TOBIND_EXTERNAL_IPS,
                                        protocol, private_ip, port,
                                        pod_ip, container_port)
                i, o, e = ssh.exec_command(new_rule)

            if not elb_rules and port:
                listeners.append((public_port, port, protocol))
        if listeners:
            sg = get_security_group(conn)
            if not sg:
                if not data.get('vpc'):
                    return False
                vpc_id = data['vpc'][0]
                sg = create_security_group(conn, vpc_id)

            elb = elbconn.create_load_balancer(
                name=service, zones=None, listeners=listeners,
                subnets=data['sn'], security_groups=sg)
            elb.register_instances(data['instances'])

            with app.app_context():
                register_elb_name(service, elb.dns_name)
                pod = Pod.query.filter(Pod.ip == pod_ip).first()
                send_event('pod:change', {'id': pod.id} if pod else None)

    elif cmd == 'del':
        if elb:
            elb.deregister_instances(data['instances'])
            elb.delete()
        for port_spec in ports:
            if not port_spec['name'].endswith('-public'):
                continue
            container_port = port_spec['targetPort']
            public_port = port_spec.get('port', container_port)
            protocol = port_spec.get('protocol', 'tcp')

            match = [i for i in rules
                     if (i.pod_ip, i.pod_port) == (pod_ip, container_port)]

            if match:
                for ruleset in match:
                    rule = compose_dnat('D', NODE_TOBIND_EXTERNAL_IPS,
                                        protocol, private_ip,
                                        ruleset.host_port,
                                        ruleset.pod_ip, ruleset.pod_port)
                    ssh.exec_command(rule)
    return True


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
            return g.user

    @classmethod
    def jsonwrap(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rv = func(*args, **kwargs)
            if isinstance(rv, Response):
                return rv
            return jsonify({'status': 'OK', 'data': rv})

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
    dt_re = re.compile(r'^\d{4}-\d{2}-\d{2}((T|\s)\d{2}:\d{2}:\d{2}Z?)?$')
    match = dt_re.match(instr)
    if not match:
        return None
    if match.group(0):
        try:
            return datetime.datetime.strptime(instr, DATE_FMT)
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(instr, DATE_FMT + ' ' + TIME_FMT)
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(instr, DATE_FMT + 'T' + TIME_FMT)
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(
                instr, DATE_FMT + 'T' + TIME_FMT + 'Z')
        except ValueError:
            pass
    return None


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


files = ['/etc/nginx/conf.d/shared-kubernetes.conf',
         '/etc/nginx/conf.d/shared-etcd.conf']
deny_all = nginx.Key('deny', 'all')


def update_allowed(accept_ips, conf):
    for server in conf.filter('Server'):
        for location in server.filter('Location'):
            if not any([key.name == 'return' and key.value == '403'
                        for key in location.keys]):
                for key in location.keys:
                    if key.name in ('allow', 'deny'):
                        location.remove(key)
                for ip in accept_ips:
                    location.add(nginx.Key('allow', ip))
                location.add(deny_all)


def update_nginx_proxy_restriction(accept_ips):
    for filename in files:
        conf = nginx.loadf(filename)
        update_allowed(accept_ips, conf)
        nginx.dumpf(conf, filename)
    subprocess.call('sudo /var/opt/kuberdock/nginx_reload.sh', shell=True)


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


def send_pod_status_update(pod_status, db_pod, event_type):
    """Sends pod status change to frontend.
    Must be executed in application context.
    """
    key_ = 'pod_state_' + db_pod.id

    redis = ConnectionPool.get_connection()
    prev_state = redis.get(key_)
    user_id = db_pod.owner_id
    if not prev_state:
        redis.set(key_, pod_status)
    else:
        current = pod_status
        deleted = event_type == 'DELETED'
        if prev_state != current or deleted:
            redis.set(key_, 'DELETED' if deleted else current)
            event = ('pod:delete'
                     if db_pod.status in ('deleting', 'deleted') else
                     'pod:change')
            send_event_to_role(event, {'id': db_pod.id}, 'Admin')
            send_event_to_user(event, {'id': db_pod.id}, user_id)
