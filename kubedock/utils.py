#import pkgutil
#import importlib

from flask import current_app, request, jsonify, g
from flask.ext.login import current_user, logout_user
from functools import wraps

from .settings import KUBE_MASTER_URL
from .users import User
from .core import ssh_connect
from .settings import NODE_TOBIND_EXTERNAL_IPS, SERVICES_VERBOSE_LOG


def login_required_or_basic(func):
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
            raise APIError('Not Authorized', status_code=401)
            #return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


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
    url = kwargs.get('url') or KUBE_MASTER_URL
    res = '{0}/{1}'.format(url, '/'.join([str(arg) for arg in args]))
    if kwargs.get('use_v3'):
        res = res.replace('v1beta2', 'v1beta3/namespaces/default')
    return res


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


def modify_node_ips(host, cmd, pod_ip, public_ip, ports):
    ARPING = 'arping -I {0} -A {1} -c 10 -w 1'
    IP_ADDR = 'ip addr {0} {1}/32 dev {2}'
    IPTABLES = 'iptables -t nat -{0} PREROUTING ' \
               '-i {1} ' \
               '-p {2} -d {3} ' \
               '--dport {4} -j DNAT ' \
               '--to-destination {5}:{6}'
    ssh, errors = ssh_connect(host)
    if errors:
        print errors
        return False
    ssh.exec_command(IP_ADDR.format(cmd, public_ip, NODE_TOBIND_EXTERNAL_IPS))
    if cmd == 'add':
        ssh.exec_command(ARPING.format(NODE_TOBIND_EXTERNAL_IPS, public_ip))
    for port_spec in ports:
        if not port_spec['name'].endswith('-public'):
            continue
        containerPort = port_spec['targetPort']
        publicPort = port_spec.get('port', containerPort)
        protocol = port_spec.get('protocol', 'tcp')
        if cmd == 'add':
            if SERVICES_VERBOSE_LOG >= 1:
                print '==ADDED PORTS==', publicPort, containerPort, protocol
            i, o, e = ssh.exec_command(
                IPTABLES.format('C', NODE_TOBIND_EXTERNAL_IPS, protocol,
                                public_ip,
                                publicPort,
                                pod_ip,
                                containerPort))
            exit_status = o.channel.recv_exit_status()
            if exit_status != 0:
                ssh.exec_command(
                    IPTABLES.format('I', NODE_TOBIND_EXTERNAL_IPS, protocol,
                                    public_ip,
                                    publicPort,
                                    pod_ip,
                                    containerPort))
        else:
            if SERVICES_VERBOSE_LOG >= 1:
                print '==DELETED PORTS==', publicPort, containerPort, protocol
            ssh.exec_command(
                IPTABLES.format('D', NODE_TOBIND_EXTERNAL_IPS, protocol,
                                public_ip,
                                publicPort,
                                pod_ip,
                                containerPort))
    ssh.close()
    return True