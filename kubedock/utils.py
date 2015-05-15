#import pkgutil
#import importlib
from json import JSONEncoder
from flask import current_app, request, jsonify, g
from flask.ext.login import current_user, logout_user
from functools import wraps

from .settings import KUBE_MASTER_URL
from .users import User
from .core import ssh_connect
from .rbac import check_permission
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
    """
    Returns URL
    :param args:
    :param kwargs:
        namespace - namespace
        use_v3 - True/False to use API version v1beta3
    :return: string
    """
    url = KUBE_MASTER_URL
    if args:
        url = '{0}/{1}'.format(url.rstrip('/'), '/'.join(map(str, args)))
    if not kwargs.get('use_v3'):
        return url
    namespace = kwargs.get('namespace', 'default')
    if namespace:
        return url.replace('v1beta2', 'v1beta3/namespaces/{0}'.format(namespace))
    return url.replace('v1beta2', 'v1beta3')


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
        
    def _get_current_user(self):
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
    
    def _get_params(self):
        data = request.json
        if data is None:
            data = request.form.to_dict()
        return data


def register_api(bp, view, endpoint, url, pk='id', pk_type='string', **kwargs):
    view_func = view.as_view(endpoint)
    bp.add_url_rule(url, view_func=view_func, methods=['GET'],
                      defaults={pk: None}, **kwargs)
    bp.add_url_rule(url, view_func=view_func, methods=['POST'], **kwargs)
    bp.add_url_rule('{0}<{1}:{2}>'.format(url, pk_type, pk),
                      view_func=view_func,
                      methods=['GET', 'PUT', 'DELETE'], **kwargs)