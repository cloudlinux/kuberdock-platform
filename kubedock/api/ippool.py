
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
from flask.views import MethodView

from kubedock.api import check_api_version
from kubedock.api.utils import use_kwargs
from kubedock.kapi.ippool import IpAddrPool
from kubedock.login import auth_required
from kubedock.rbac import check_permission
from kubedock.utils import KubeUtils, API_VERSIONS, register_api
from kubedock.validation.schemas import boolean


ippool = Blueprint('ippool', __name__, url_prefix='/ippool')


class IPPoolAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, auth_required]

    @check_permission('get', 'ippool')
    @use_kwargs({'free-only': boolean}, allow_unknown=True)
    def get(self, network=None, **params):
        if check_api_version([API_VERSIONS.v2]):
            if network:
                return IpAddrPool.get_network_ips(network)
            else:
                return IpAddrPool.get_networks_list()
        page = int(params.get('page', 1))
        return IpAddrPool.get(network, page, params.get('free-only'))

    @check_permission('create', 'ippool')
    @use_kwargs({}, allow_unknown=True)
    def post(self, **params):
        pool = IpAddrPool.create(params)

        if check_api_version([API_VERSIONS.v2]):
            return IpAddrPool.get_network_ips(params['network'])
        return pool.to_dict(page=1)

    @check_permission('edit', 'ippool')
    @use_kwargs({}, allow_unknown=True)
    def put(self, network, **params):
        net = IpAddrPool.update(network, params)
        if check_api_version([API_VERSIONS.v2]):
            return IpAddrPool.get_network_ips(network)
        return net.to_dict()

    patch = put

    @check_permission('delete', 'ippool')
    def delete(self, network):
        return IpAddrPool.delete(network)


register_api(ippool, IPPoolAPI, 'ippool', '/', 'network', 'path')


@ippool.route('/userstat', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_user_address():
    user = KubeUtils.get_current_user()
    return IpAddrPool.get_user_addresses(user)


@ippool.route('/get-public-ip/<path:node>/<path:pod>', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_public_ip(node, pod):
    return IpAddrPool.assign_ip_to_pod(pod, node)
