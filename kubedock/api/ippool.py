
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

from flask import Blueprint

from kubedock.api import check_api_version
from ..login import auth_required
from ..utils import KubeUtils, API_VERSIONS
from ..kapi.ippool import IpAddrPool
from ..rbac import check_permission


ippool = Blueprint('ippool', __name__, url_prefix='/ippool')


@ippool.route('/', methods=['GET'])
@ippool.route('/<path:network>', methods=['GET'])
@auth_required
@check_permission('get', 'ippool')
@KubeUtils.jsonwrap
def get_ippool(network=None):
    params = KubeUtils._get_params()
    if 'free-only' in params:
        return IpAddrPool.get_free()
    if check_api_version([API_VERSIONS.v2]):
        if network:
            return IpAddrPool.get_network_ips(network)
        else:
            return IpAddrPool.get_networks_list()
    page = int(params.get('page', 1))
    return IpAddrPool.get(network, page)


# @ippool.route('/getFreeHost', methods=['GET'])
# @auth_required
# @KubeUtils.jsonwrap
# def get_free_address():
#     return IpAddrPool().get_free()


@ippool.route('/userstat', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_user_address():
    user = KubeUtils.get_current_user()
    return IpAddrPool.get_user_addresses(user)


@ippool.route('/', methods=['POST'])
@auth_required
@check_permission('create', 'ippool')
@KubeUtils.jsonwrap
def create_item():
    params = KubeUtils._get_params()
    pool = IpAddrPool.create(params)

    if check_api_version([API_VERSIONS.v2]):
        return IpAddrPool.get_network_ips(params['network'])
    return pool.to_dict(page=1)


@ippool.route('/<path:network>', methods=['PUT'])
@auth_required
@check_permission('edit', 'ippool')
@KubeUtils.jsonwrap
def update_ippool(network):
    params = KubeUtils._get_params()
    net = IpAddrPool.update(network, params)
    if check_api_version([API_VERSIONS.v2]):
        return IpAddrPool.get_network_ips(network)
    return net.to_dict()


@ippool.route('/<path:network>', methods=['DELETE'])
@auth_required
@check_permission('delete', 'ippool')
@KubeUtils.jsonwrap
def delete_ippool(network):
    return IpAddrPool.delete(network)


@ippool.route('/get-public-ip/<path:node>/<path:pod>', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_public_ip(node, pod):
    return IpAddrPool.assign_ip_to_pod(pod, node)


@ippool.route('/mode', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_mode():
    return IpAddrPool.get_mode()
