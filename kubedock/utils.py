import bitmath
import boto.ec2
import boto.ec2.elb
import json
import os
import random
import re
import socket
import sys
import datetime

from collections import namedtuple
from flask import current_app, request, jsonify, g, has_app_context
from flask.ext.login import current_user, logout_user
from functools import wraps
from itertools import chain
from json import JSONEncoder
from sqlalchemy.exc import SQLAlchemyError, InvalidRequestError
from traceback import format_exception

from .settings import KUBE_MASTER_URL, KUBE_API_VERSION
from .billing import Kube
from .pods import Pod
from .core import ssh_connect, db, ConnectionPool
from .settings import NODE_TOBIND_EXTERNAL_IPS, PODS_VERBOSE_LOG


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


def get_channel_key(conn, key, size=100):
    """
    Gets the last cache id for channel. If keys amount exceeds size truncate keys
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
        for k in keys[:-(size-1)]:
            conn.hdel(key, k)
    return int(keys[-1])+1


def send_event(event_name, data, to_file=None, channel='common', prefix='SSEEVT'):
    """
    Sends event via pubsub to all subscribers and cache it to be rolled back
    if missed
    @param event_name: string -> event name
    @param data: dict -> data to be sent
    @param to_file: file handle object -> file object to output logs
    @param channel: string -> target identifier for event to be sent to
    @param prefix: string -> redis key prefix to store channel cache
    """
    conn = ConnectionPool.get_connection()
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


def send_logs(node, data, to_file=None, channel='common'):
    conn = ConnectionPool.get_connection()
    conn.publish(channel, json.dumps(
        [None, 'node:installLog', {'id': node, 'data': data}]))
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
    :return: string
    """
    api_version = kwargs.get('api_version', KUBE_API_VERSION)
    url = '/'.join([KUBE_MASTER_URL.rstrip('/'), api_version])
    if args:
        url = '{0}/{1}'.format(url.rstrip('/'), '/'.join(map(str, args)))
    namespace = kwargs.get('namespace', 'default')
    if namespace:
        url = url.replace('/' + api_version,
                          '/{0}/namespaces/{1}'.format(api_version, namespace),
                          1)
    if kwargs.get('watch'):
        url = url.replace('http://', 'ws://') + '?watch=true'
    return url


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


# separate function because set_roles_loader decorator don't return function. Lib bug.
def get_user_role():
    rolename = 'AnonymousUser'
    try:
        rolename = current_user.role.rolename
    except AttributeError:
        try:
            rolename = g.user.role.rolename
        except AttributeError:
            pass
    if rolename == 'AnonymousUser':
        logout_user()
    return rolename


class APIError(Exception):
    message = 'Unknown error'
    status_code = 400

    def __init__(self, message=None, status_code=None, type=None):
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        if type is not None:
            self.type = type

    def __str__(self):
        # Only message because this class may wrap other exception classes
        return self.message

    def __repr__(self):
        return '<{0}: "{1}" ({2})>'.format(
            self.__class__.__name__, self.message, self.status_code)


class PermissionDenied(APIError):
    status_code = 403

    def __init__(self, message=None, status_code=None, type=None):
        if message is None:
            message = 'Denied to {0}'.format(get_user_role())
        super(PermissionDenied, self).__init__(message, status_code, type)


class NotAuthorized(APIError):
    message = 'Not Authorized'
    status_code = 401


class atomic(object):
    """Wrap code in transaction. Can be used as decorator or context manager.

    If the block of code is successfully completed, the transaction is committed.
    If there is an exception, the transaction is rolled back.
    Saves you from repeating `try-except-rollback` and adds `commit=True/False`
    parameter to decorated functions.
    You can find some usage examples in `.tests.utils.TestAtomic` or `.kapi.users`.

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
        nested = self.nested if self.nested_override is None else self.nested_override
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
        msg = ("Prevented attempt to close main transaction inside `atomic` block.\n"
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
        db.event.listen(db.session, 'after_soft_rollback', cls._unexpectedly_closed)

    @classmethod
    def unregister(cls):
        try:
            db.event.remove(db.session, 'before_commit', cls._unexpectedly_closed)
            db.event.remove(db.session, 'after_soft_rollback', cls._unexpectedly_closed)
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
    Gets amazon instance by internal DNS name and return instance id and some misc info
    :param conn: object -> boto ec2 connection object
    :param name: string -> instance internal DNS name
    :return: dict -> dict of arrays: instances, security groups, subnets and VPCs
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
    return {'instances': instances, 'sg': list(sg), 'sn': list(sn), 'vpc': list(vpc)}


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
    Gets all node iptables DNAT rules. Get host port, pod IP, pod port for a rule
    :param conn: object -> ssh connection object
    :return: list -> list of namedtuples of data (host_port, pod_ip, pod_port)
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
    We name our load balancers after service name. A load balancer may have more
    than one listener entity, so we get load balancer by name and then get its
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
        (Pod.status!='deleted')&(Pod.config.like('%'+service+'%'))).first()
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
        (Pod.status!='deleted')&(Pod.config.like('%'+service+'%'))).first()
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
                                          protocol, private_ip, ruleset.host_port,
                                          ruleset.pod_ip, ruleset.pod_port)
                    ssh.exec_command(rule)
    return True


def unregistered_pod_warning(pod_id):
    current_app.logger.warn('Pod with id {0} is not registered in Kuberdock '
                            'database, but was found in kubernetes.'.format(pod_id))


def pod_without_id_warning(name, namespace):
    current_app.logger.warn(
        'Pod with metadata.name {0} and metadata.namesapce {1} have no '
        'kuberdock-pod-uid. Maybe someone created it using kubernetes, '
        'bypass kuberdock.'.format(name, namespace))


def set_limit(host, pod_id, containers, app):
    ssh, errors = ssh_connect(host)
    if errors:
        print errors
        return False
    with app.app_context():
        spaces = dict(
            (i, (s, u)) for i, s, u in Kube.query.values(
                Kube.id, Kube.disk_space, Kube.disk_space_units
                )
            )  #workaround

        pod = Pod.query.filter_by(id=pod_id).first()

        if pod is None:
            unregistered_pod_warning(pod_id)
            return False

        config = json.loads(pod.config)
        kube_type = config['kube_type']
        #kube = Kube.query.get(kube_type) this query raises an exception
    limits = []
    for container in config['containers']:
        container_name = container['name']
        if container_name not in containers:
            continue
        #disk_space = kube.disk_space * container['kubes']
        space, unit = spaces.get(kube_type, (0, 'GB'))
        disk_space = space * container['kubes']
        disk_space_unit = unit[0].lower() if unit else ''
        if disk_space_unit not in ('', 'k', 'm', 'g', 't'):
            disk_space_unit = ''
        disk_space_str = '{0}{1}'.format(disk_space, disk_space_unit)
        limits.append((containers[container_name], disk_space_str))
    limits_repr = ' '.join('='.join(limit) for limit in limits)
    _, o, e = ssh.exec_command(
        'python /var/lib/kuberdock/scripts/fslimit.py {0}'.format(limits_repr)
    )
    exit_status = o.channel.recv_exit_status()
    if exit_status > 0:
        if PODS_VERBOSE_LOG >= 2:
            print 'O', o.read()
            print 'E', e.read()
        print 'Error fslimit.py with exit status {0}'.format(exit_status)
        ssh.close()
        return False
    ssh.close()
    return True


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
    #pretty ugly. Wants refactoring
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
    return params


class KubeUtils(object):

    @staticmethod
    def _get_current_user():
        try:
            current_user.username
            return current_user
        except AttributeError:
            return g.user

    @classmethod
    def jsonwrap(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return jsonify({'status': 'OK', 'data': func(*args, **kwargs)})
        return wrapper

    @classmethod
    def pod_start_permissions(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = cls._get_current_user()
            params = cls._get_params()
            if ('command' in params and params['command'] in ['start'] or params) and user.suspended is True:
                raise PermissionDenied('Permission denied. User suspended. +  Your package has expired. Please upgrade it.')
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
    :param rtype: return type (default: int if unit is 'Byte' or precision <= 0, float otherwize)
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


def update_nginx_proxy_restriction(accept_ips):
    pass
    # modification of shared-etcd.conf and shared-kubernetes.conf need to be
    # done here to allow access only from accept_ips
