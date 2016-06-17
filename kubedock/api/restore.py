from flask import Blueprint

from kubedock.api.utils import use_kwargs
from kubedock.backups import pods as backup_pods
from kubedock.decorators import maintenance_protected
from kubedock.exceptions import PermissionDenied, APIError
from kubedock.kapi.users import UserNotFound
from kubedock.login import auth_required
from kubedock.rbac import check_permission, check_permission_for_user
from kubedock.users import User
from kubedock.utils import KubeUtils

restore = Blueprint('restore', __name__, url_prefix='/restore')


def _get_user(username):
    user = User.get(username)
    if user is None:
        raise UserNotFound('User "{0}" does not exist'.format(username))
    return user


pods_args_schema = {
    'pod_data': {
        'type': 'dict',
        'required': True
    },
    'owner': {
        'coerce': _get_user,
        'required': True,
        'nullable': False
    },
    'volumes_dir_url': {
        'type': 'string',
        'required': False,
        'nullable': True
    }
}


@restore.route('/pod', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@check_permission('restore_for_another', 'pods')
@use_kwargs(pods_args_schema)
@KubeUtils.jsonwrap
def pods(pod_data, owner, volumes_dir_url=None):
    if not check_permission_for_user(owner, 'create', 'pods'):
        raise PermissionDenied(
            'Forbidden create new pod for user %s' % owner)
    try:
        return backup_pods.restore(
            pod_data=pod_data, owner=owner,
            volumes_dir_url=volumes_dir_url)
    except Exception as e:
        if isinstance(e, APIError):
            raise e
        else:
            raise APIError(e.message, type=type(e).__name__)
