from flask import Blueprint, request, current_app

from datetime import datetime

from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError
from kubedock.login import auth_required
from kubedock.core import db
from kubedock.kapi.nginx_utils import update_nginx_proxy_restriction
from kubedock.kapi.network_policies import get_rhost_policy
from kubedock.nodes.models import RegisteredHost
from kubedock.utils import Etcd, KubeUtils, atomic
from kubedock.settings import (CALICO, ETCD_REGISTERED_HOSTS,
                               ETCD_NETWORK_POLICY_HOSTS)

hosts = Blueprint('hosts', __name__, url_prefix='/hosts')


@hosts.route('/register', methods=['POST'])
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def create_host():
    user = KubeUtils.get_current_user()
    if not user.is_administrator():
        raise APIError('Insufficient permissions level', 403,
                       type='PermissionDenied')
    ip = request.environ.get('REMOTE_ADDR')
    return register_host(ip)


@atomic(nested=False)
def register_host(ip):
    current_app.logger.info('REGISTERING REMOTE HOST IN KD NETWORK, IP: {}'
                            .format(ip))
    host = RegisteredHost.query.filter_by(host=ip).first()
    if host is not None:
        raise APIError('Host is already registered', 409, type='data exist')
    db.session.add(RegisteredHost(host=ip, time_stamp=datetime.now()))
    if not CALICO:
        Etcd(ETCD_REGISTERED_HOSTS).put(ip)
    accept_ips = [registered.host for registered in RegisteredHost.query]
    update_nginx_proxy_restriction(accept_ips)
    policy = get_rhost_policy(ip)
    policy_hosts = Etcd(ETCD_NETWORK_POLICY_HOSTS)
    current_app.logger.debug('GENERATED POLICY FOR REMOTE HOST IS: {}'
                             .format(policy))
    policy_hosts.put(ip, value=policy)
    return {'ip': ip}
