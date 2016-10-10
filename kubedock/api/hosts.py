from flask import Blueprint, redirect, request, current_app

from datetime import datetime
from urlparse import urlparse, urlunparse

from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError
from kubedock.login import auth_required
from kubedock.core import db
from kubedock.kapi.nginx_utils import update_nginx_proxy_restriction
from kubedock.kapi.network_policies import get_rhost_policy
from kubedock.nodes.models import RegisteredHost
from kubedock.utils import Etcd, KubeUtils, atomic, fix_calico, get_ip_address
from kubedock.settings import (CALICO, ETCD_REGISTERED_HOSTS,
                               ETCD_NETWORK_POLICY_HOSTS)

hosts = Blueprint('hosts', __name__, url_prefix='/hosts')


@hosts.route('/register', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def create_host():
    user = KubeUtils.get_current_user()
    if not user.is_administrator():
        raise APIError('Insufficient permissions level', 403,
                       type='PermissionDenied')
    ip = request.environ.get('REMOTE_ADDR')
    if CALICO:
        return register_host_calico(ip)
    else:
        return register_host(ip)


# TODO merge both registrations to one, because old is not needed anymore
@atomic(nested=False)
def register_host(ip):
    host = RegisteredHost.query.filter_by(host=ip).first()
    if host is not None:
        raise APIError('Host is already registered', 409, type='data exist')
    db.session.add(RegisteredHost(host=ip, time_stamp=datetime.now()))
    if not CALICO:
        Etcd(ETCD_REGISTERED_HOSTS).put(ip)
    accept_ips = [registered.host for registered in RegisteredHost.query]
    update_nginx_proxy_restriction(accept_ips)
    return {'ip': ip}


# def register_host_calico_OLD(ip):
#     # request should be performed from Calico network
#     tunl_ip = get_ip_address('tunl0')  # Calico interface
#     if tunl_ip is None:
#         raise APIError('Failed to get Calico interface IP address', 500)
#     if request.environ.get('HTTP_HOST') != tunl_ip:
#         try:
#             return register_host(ip)
#         except APIError as e:
#             if e.type != 'data exist':
#                 raise
#         # fix issue when sometimes calico network is unreachable
#         # Not needed with correct policy:
#         # fix_calico(ip)
#         # replace host with Calico IP and redirect to it
#         url = urlparse(request.url)
#         netloc = tunl_ip
#         if url.port is not None:
#             netloc = '{0}:{1}'.format(netloc, url.port)
#         url = url._replace(netloc=netloc)
#         new_url = urlunparse(url)
#         return redirect(new_url, code=307)
#     policy_hosts = Etcd(ETCD_NETWORK_POLICY_HOSTS)
#     if policy_hosts.exists(ip):
#         raise APIError('Host is already registered', 409, type='data exist')
#     policy_hosts.put(ip, value=get_rhost_policy(ip))
#     return {'ip': ip}


def register_host_calico(ip):
    current_app.logger.info('REGISTERING REMOTE HOST IN KD NETWORK, IP: {}'
                            .format(ip))
    try:
        return register_host(ip)
    except APIError as e:
        if e.type != 'data exist':
            raise
    # We need registration twice - ones for access to etcd and ones for
    # creating correct hosts policy that include Calico tunnel ip address,
    # so we do second step anyway, even if host is already registered
    policy, err = get_rhost_policy(ip)
    if policy is None:
        if err:
            current_app.logger.error(err)
            raise APIError("Error during registering host")
        else:
            # This is a case for first registration when calico node is not
            # ready and does't have tunnel ip yet
            return {'ip': ip}
    policy_hosts = Etcd(ETCD_NETWORK_POLICY_HOSTS)
    current_app.logger.debug('GENERATED POLICY FOR REMOTE HOST IS: {}'
                             .format(policy))
    policy_hosts.put(ip, value=policy)
    if policy_hosts.exists(ip):
        raise APIError('Host is already registered, updating rules', 409,
                       type='data exist')
    return {'ip': ip}
