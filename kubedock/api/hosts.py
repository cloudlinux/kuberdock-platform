from flask import Blueprint, redirect, request

import subprocess
from datetime import datetime
from urlparse import urlparse, urlunparse

from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError
from kubedock.login import auth_required
from kubedock.core import db
from kubedock.kapi.nginx_utils import update_nginx_proxy_restriction
from kubedock.nodes.models import RegisteredHost
from kubedock.utils import Etcd, KubeUtils, atomic, get_ip_address
from kubedock.settings import (CALICO, ETCD_BASE_URL, ETCD_REGISTERED_HOSTS,
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


def register_host_calico(ip):
    # request should be performed from Calico network
    tunl_ip = get_ip_address('tunl0')  # Calico interface
    if tunl_ip is None:
        raise APIError('Failed to get Calico interface IP address', 500)
    if request.environ.get('HTTP_HOST') != tunl_ip:
        try:
            return register_host(ip)
        except APIError as e:
            if e.type != 'data exist':
                raise
        # fix issue when sometimes calico network is unreachable
        fix_calico(ip)
        # replace host with Calico IP and redirect to it
        url = urlparse(request.url)
        netloc = tunl_ip
        if url.port is not None:
            netloc = '{0}:{1}'.format(netloc, url.port)
        url = url._replace(netloc=netloc)
        new_url = urlunparse(url)
        return redirect(new_url, code=307)
    policy_hosts = Etcd(ETCD_NETWORK_POLICY_HOSTS)
    if policy_hosts.exists(ip):
        raise APIError('Host is already registered', 409, type='data exist')
    policy_hosts.put(ip, value=get_host_policy(ip))
    return {'ip': ip}


def get_host_policy(ip):
    return {
        "id": ip,
        "order": 10,
        "inbound_rules": [{
            "action": "allow",
            "src_net": "{0}/32".format(ip)
        }],
        "outbound_rules": [{
            "action": "allow"
        }],
        "selector": ""
    }


def _find_calico_host(nodes, ip):
    for node in nodes:
        for sub_node in node['nodes']:
            if sub_node.get('value') == ip:
                return node['key'].split('/')[-1]


def fix_calico(ip):
    """
    Fix issue when Calico network is unreachable from extra host --
      ping probe from master "discovers" the network
    :param ip: extra host IP
    """
    etcd = Etcd(ETCD_BASE_URL)

    # get hostname by ip
    try:
        nodes = etcd.get('/calico/bgp/v1/host', recursive=True)['node']['nodes']
    except (KeyError, Etcd.RequestException):
        raise APIError("Can't get Calico nodes")

    host = _find_calico_host(nodes, ip)
    if host is None:
        APIError("Can't find node {0} in Calico".format(ip))

    # get ip in calico network by hostname
    try:
        key = '/calico/ipam/v2/host/{0}/ipv4/block'.format(host)
        block = etcd.get(key)['node']['nodes'][0]['key']
    except (KeyError, IndexError, Etcd.RequestException):
        raise APIError("Can't find Calico ipam block for {0}".format(host))

    calico_ip = block.split('/')[-1].split('-')[0]

    # ping probe
    subprocess.call(['ping', '-c', '1', calico_ip])
