from flask import Blueprint

from kubedock.api.utils import use_kwargs
from kubedock.backups import pods as backup_pods
from kubedock.decorators import maintenance_protected
from kubedock.login import auth_required
from kubedock.rbac import check_permission
from kubedock.utils import KubeUtils
from kubedock.validation import owner_mandatory_schema

restore = Blueprint('restore', __name__, url_prefix='/restore')


pods_args_schema = {
    'pod_data': {
        'type': 'dict',
        'required': True
    },
    'owner': owner_mandatory_schema,
    'volumes_dir_url': {
        'type': 'string',
        'required': False,
        'nullable': True
    }
}


@restore.route('/pod', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@check_permission('create_non_owned', 'pods')
@KubeUtils.jsonwrap
@use_kwargs(pods_args_schema)
def pods(pod_data, owner, volumes_dir_url=None):
    with check_permission('own', 'pods', user=owner):
        return backup_pods.restore(
            pod_data=pod_data, owner=owner, volumes_dir_url=volumes_dir_url)
