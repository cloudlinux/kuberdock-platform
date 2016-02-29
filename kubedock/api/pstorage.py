from flask import Blueprint
from flask.views import MethodView

from . import APIError
from ..decorators import login_required_or_basic_or_token
from ..utils import KubeUtils, register_api
from ..kapi import pstorage as ps
from ..pods.models import PersistentDisk
from ..nodes.models import Node
from ..rbac import check_permission


pstorage = Blueprint('pstorage', __name__, url_prefix='/pstorage')


class PDNotFound(APIError):
    message = 'Persistent disk not found.'
    status_code = 404


class PDIsUsed(APIError):
    message = 'Persistent disk is used.'


class PersistentStorageAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, check_permission('get', 'pods'),
                  login_required_or_basic_or_token]

    @staticmethod
    def _resolve_storage():
        storage_cls = ps.get_storage_class()
        return storage_cls or ps.PersistentStorage

    def get(self, device_id):
        params = self._get_params()
        user = self._get_current_user()
        cls = self._resolve_storage()
        if params.get('free-only') == 'true':
            return map(add_kube_type, cls().get_user_unmapped_drives(user))
        if device_id is None:
            return map(add_kube_type, cls().get_by_user(user))
        return add_kube_type(cls().get_by_user(user, device_id))

    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        name, size = params.get('name', ''), params.get('size', 1)
        pd = PersistentDisk.query.filter_by(name=name).first()
        if pd is not None:
            raise APIError('{0} already exists'.format(name), 406)
        pd = PersistentDisk(size=size, owner=user, name=name)
        Storage = self._resolve_storage()
        data = Storage().create(pd)
        if data is None:
            raise APIError('Couldn\'t create drive.')
        try:
            pd.save()
        except Exception:
            ps.delete_drive_by_id(data['id'])
            raise APIError('Couldn\'t save persistent disk.')
        return add_kube_type(data)

    def put(self, device_id):
        pass

    def delete(self, device_id):
        pd = PersistentDisk.get_all_query().filter(
            PersistentDisk.id == device_id
        ).first()
        if pd is None:
            raise PDNotFound()
        if pd.owner_id != self._get_current_user().id:
            raise APIError('Volume does not belong to current user', 403)
        if pd.pod_id is not None:
            raise PDIsUsed()
        allow_flag, description = ps.drive_can_be_deleted(device_id)
        if not allow_flag:
            raise APIError(
                'Volume can not be deleted. Reason: {}'.format(description)
            )
        ps.delete_drive_by_id(device_id)


def add_kube_type(disk):
    node = disk.get('node_id')
    if node is not None:
        node = Node.query.get(node)
    disk['kube_type'] = None if node is None else node.kube_id
    return disk


register_api(pstorage, PersistentStorageAPI, 'pstorage', '/', 'device_id', strict_slashes=False)
