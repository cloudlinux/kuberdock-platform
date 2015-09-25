import bitmath
import boto.ec2
import boto.ec2.elb
import json
import random
import re
import socket
import datetime

from collections import namedtuple
from flask import current_app, request, jsonify, g
from flask.ext.login import current_user, logout_user
from functools import wraps
from itertools import chain
from json import JSONEncoder

from .settings import KUBE_MASTER_URL, KUBE_API_VERSION
from .billing import Kube
from .pods import Pod
from .users import User
from .core import ssh_connect, db, ConnectionPool
from .rbac import check_permission, PermissionDenied
from .settings import NODE_TOBIND_EXTERNAL_IPS, SERVICES_VERBOSE_LOG, AWS, PODS_VERBOSE_LOG
from kubedock.updates.helpers import get_maintenance


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



def login_required_or_basic_or_token(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_app.login_manager._login_disabled:
            return func(*args, **kwargs)
        if not current_user.is_authenticated():
            if request.authorization is not None:
                username = request.authorization.get('username', None)
                passwd = request.authorization.get('password', None)
                if username is not None and passwd is not None:
                    user = User.query.filter_by(username=username).first()
                    if user is not None and user.verify_password(passwd):
                        g.user = user
                        return func(*args, **kwargs)
            token = request.args.get('token')
            if token:
                user = User.query.filter_by(token=token).first()
                if user is not None:
                    g.user = user
                    return func(*args, **kwargs)
            raise APIError('Not Authorized', status_code=401)
            #return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


def maintenance_protected(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if get_maintenance():
            raise APIError("Sorry, Kuberdock now is in maintenance mode, please, wait until it finishes upgrade and try again")
        return func(*args, **kwargs)
    return wrapped


def send_event(event_name, data, to_file=None, channel='common'):
    conn = ConnectionPool.get_connection()
    conn.publish(channel, json.dumps([event_name, data]))
    if to_file is not None:
        try:
            to_file.write(data)
            to_file.write('\n')
            to_file.flush()
        except Exception as e:
            print 'Error writing to log file', e.__repr__()


def send_logs(node, data, to_file=None, channel='common'):
    conn = ConnectionPool.get_connection()
    conn.publish(channel, json.dumps(['install_logs',
                                      {'for_node': node, 'data': data}]))
    if to_file is not None:
        try:
            to_file.write(data)
            to_file.write('\n')
            to_file.flush()
        except Exception as e:
            print 'Error writing to log file', e.__repr__()


def check_perms(rolename):
    roles = ['User', 'Administrator']

    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            role = get_user_role()
            if rolename not in roles or roles.index(role) < roles.index(rolename):
                response = jsonify({'code': 403, 'message': 'Access denied'})
                response.status_code = 403
                return response
            return func(*args, **kwargs)
        return decorated_view
    return wrapper


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
        url = url.replace('http', 'ws') + '?watch=true'
    return url


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
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code


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


def compose_dnat(*params):
    """
    Composes iptables DNAT rule
    :param params: array of positional params
    :return: string -> iptables rule
    """
    IPTABLES = ('iptables -t nat -{0} PREROUTING -i {1} -p {2} '
               '-d {3} --dport {4} -j DNAT --to-destination {5}:{6}')
    return IPTABLES.format(*params)


def compose_mark(*params):
    """
    Composes iptables FORWARD rule to mark packets with user ID
    :param params: array of positional params
    :return: string -> iptables rule
    """
    IPTABLES = ('iptables -{0} FORWARD -i docker0 -o docker0 '
                '-s {1} -j MARK --set-mark {2}')
    return IPTABLES.format(*params)


def compose_check(*params):
    """
    Composes iptables FORWARD rule to check packets by user ID
    :param params: array of positional params
    :return: string -> iptables rule
    """
    IPTABLES = ('iptables -{0} FORWARD -i docker0 -o docker0 '
                '-d {1} -m mark ! --mark {2} -j REJECT')
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


def handle_generic_node(ssh, service, cmd, pod_ip, public_ip, ports, app):
    """
    Handles IP addresses and iptables rules on non-amazon node
    :param service: string -> service name
    :param host: string -> node hostname
    :param pod_ip: string -> IP address of a node pod
    :param public_ip: string -> public IP address from the IP pool
    :param ports: list -> list of port dicts
    :return: boolean
    """
    i, o, e = ssh.exec_command(
        'bash /var/lib/kuberdock/scripts/modify_ip.sh {0} {1} {2}'
        .format(cmd, public_ip, NODE_TOBIND_EXTERNAL_IPS)
    )
    exit_status = o.channel.recv_exit_status()
    if exit_status > 0:
        if SERVICES_VERBOSE_LOG >= 2:
            print 'O', o.read()
            print 'E', e.read()
        print 'Error modify_ip.sh with exit status {0} public_ip={1} IFACE={2}'\
            .format(exit_status, public_ip, NODE_TOBIND_EXTERNAL_IPS)
        return False

    for port_spec in ports:
        if not port_spec['name'].endswith('-public'):
            continue
        container_port = port_spec['targetPort']
        public_port = port_spec.get('port', container_port)
        protocol = port_spec.get('protocol', 'tcp')
        params = (NODE_TOBIND_EXTERNAL_IPS, protocol, public_ip, public_port,
                  pod_ip, container_port, service)
        if cmd == 'add':
            if SERVICES_VERBOSE_LOG >= 1:
                print '==ADDED PORTS==', public_port, container_port, protocol
            i, o, e = ssh.exec_command(compose_dnat('C', *params))
            exit_status = o.channel.recv_exit_status()
            if exit_status != 0:
                ssh.exec_command(compose_dnat('I', *params))
        else:
            if SERVICES_VERBOSE_LOG >= 1:
                print '==DELETED PORTS==', public_port, container_port, protocol
            ssh.exec_command(compose_dnat('D', *params))
    return True


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
                send_event('pull_pods_state', 'elb-ready')

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


def set_bridge_rules(ssh, service, cmd, pod_ip, app):
    """
    Sets docker bridge iptables rules to intercontainer communication for containers
    belonging to a same user
    :param ssh: object -> ssh connection object
    :param service: string -> service name
    :param cmd: string -> command (currently 'add' and 'del')
    :param pod_ip: string -> pod ip address
    """
    if app is None:
        return
    with app.app_context():
        user_id = get_pod_owner_id(service)
    if cmd == 'add':
        for routine in compose_mark, compose_check:
            i, o, e = ssh.exec_command(routine('C', pod_ip, user_id))
            exit_status = o.channel.recv_exit_status()
            if exit_status != 0:
                ssh.exec_command(routine('I', pod_ip, user_id))
    elif cmd == 'del':
        for routine in compose_mark, compose_check:
            ssh.exec_command(routine('D', pod_ip, user_id))


def modify_node_ips(service, host, cmd, pod_ip, public_ip, ports, app=None):
    ssh, errors = ssh_connect(host)
    if errors:
        return False
    if AWS:
        result = handle_aws_node(ssh, service, host, cmd, pod_ip, ports, app)
    else:
        result = handle_generic_node(ssh, service, cmd, pod_ip, public_ip, ports, app)
    set_bridge_rules(ssh, service, cmd, pod_ip, app)
    ssh.close()
    return result


def unregistered_pod_warning(pod_id):
    current_app.logger.warn('Pod with id {0} is not registered in Kuberdock '
                            'database, but was found in kubernetes.'.format(pod_id))


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
        #disk_space = kube.disk_space * container['kubes']
        space, unit = spaces.get(kube_type, (0, 'MB'))
        disk_space = space * container['kubes']
        disk_space_unit = unit[0].lower() if unit else ''
        if disk_space_unit not in ('', 'k', 'm', 'g', 't'):
            disk_space_unit = ''
        disk_space_str = '{0}{1}'.format(disk_space, disk_space_unit)
        limits.append((containers[container['name']], disk_space_str))
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
    def pod_permissions(cls, func):
        def inner(*args, **kwargs):
            rv = check_permission('get', 'pods')(func)
            return rv(*args, **kwargs)
        return inner

    @classmethod
    def pod_start_permissions(cls, func):
        def wrapper(*args, **kwargs):
            user = cls._get_current_user()
            params = cls._get_params()
            if ('command' in params and params['command'] in ['start'] or params) and user.suspended is True:
                raise PermissionDenied('Permission denied. User suspended.')
            return func(*args, **kwargs)
        return wrapper

    @staticmethod
    def _get_params():
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


def register_api(bp, view, endpoint, url, pk='id', pk_type='string', **kwargs):
    view_func = view.as_view(endpoint)
    bp.add_url_rule(url, view_func=view_func, methods=['GET'],
                    defaults={pk: None}, **kwargs)
    bp.add_url_rule(url, view_func=view_func, methods=['POST'], **kwargs)
    bp.add_url_rule('{0}<{1}:{2}>'.format(url, pk_type, pk),
                    view_func=view_func,
                    methods=['GET', 'PUT', 'DELETE'], **kwargs)


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
    dt_re = re.compile(r'^\d{4}-\d{2}-\d{2}(T|\s\d{2}:\d{2}:\d{2}Z?)?$')
    match = dt_re.match(instr)
    if not match:
        return None
    if match.groups(0):
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
    else:
        try:
            return datetime.datetime.strptime(instr, DATE_FMT)
        except ValueError:
            pass
    return None
