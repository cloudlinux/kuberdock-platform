from flask import Blueprint

from ..login import auth_required
from ..utils import KubeUtils
from ..kapi.ippool import IpAddrPool
from ..rbac import check_permission


ippool = Blueprint('ippool', __name__, url_prefix='/ippool')


@ippool.route('/', methods=['GET'], strict_slashes=False)
@ippool.route('/<path:network>', methods=['GET'], strict_slashes=False)
@auth_required
@check_permission('get', 'ippool')
@KubeUtils.jsonwrap
def get_ippool(network=None):
    params = KubeUtils._get_params()
    if 'free-only' in params:
        return IpAddrPool().get_free()
    page = int(params.get('page', 1))
    return IpAddrPool().get(network, page)


# @ippool.route('/getFreeHost', methods=['GET'], strict_slashes=False)
# @auth_required
# @KubeUtils.jsonwrap
# def get_free_address():
#     return IpAddrPool().get_free()


@ippool.route('/userstat', methods=['GET'], strict_slashes=False)
@auth_required
@KubeUtils.jsonwrap
def get_user_address():
    user = KubeUtils._get_current_user()
    return IpAddrPool().get_user_addresses(user)


@ippool.route('/', methods=['POST'], strict_slashes=False)
@auth_required
@check_permission('create', 'ippool')
@KubeUtils.jsonwrap
def create_item():
    params = KubeUtils._get_params()
    return IpAddrPool().create(params)


@ippool.route('/<path:network>', methods=['PUT'], strict_slashes=False)
@auth_required
@check_permission('edit', 'ippool')
@KubeUtils.jsonwrap
def update_ippool(network):
    params = KubeUtils._get_params()
    return IpAddrPool().update(network, params)


@ippool.route('/<path:network>', methods=['DELETE'], strict_slashes=False)
@auth_required
@check_permission('delete', 'ippool')
@KubeUtils.jsonwrap
def delete_ippool(network):
    return IpAddrPool().delete(network)
