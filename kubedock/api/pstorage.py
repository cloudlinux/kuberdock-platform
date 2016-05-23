from collections import Sequence

from flask import Blueprint
from flask.views import MethodView

from ..exceptions import APIError
from ..login import auth_required
from ..kapi import pstorage as ps
from ..nodes.models import Node
from ..pods.models import PersistentDisk
from ..rbac import check_permission
from ..utils import KubeUtils, register_api
from ..validation import V, pd_schema

pstorage = Blueprint('pstorage', __name__, url_prefix='/pstorage')


class PDNotFound(APIError):
    message = 'Persistent disk not found.'
    status_code = 404


class PDIsUsed(APIError):
    message = 'Persistent disk is used.'


class PersistentStorageAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, check_permission('get', 'pods'),
                  auth_required]

    @staticmethod
    def _resolve_storage():
        storage_cls = ps.get_storage_class()
        return storage_cls or ps.PersistentStorage

    def get(self, device_id):
        params = self._get_params()
        user = self._get_current_user()
        cls = self._resolve_storage()
        if params.get('free-only') == 'true':
            return add_kube_types(cls().get_user_unmapped_drives(user))
        if device_id is None:
            return add_kube_types(cls().get_by_user(user))
        disks = cls().get_by_user(user, device_id)
        if not disks:
            raise PDNotFound()
        return add_kube_types(disks)

    def post(self):
        user = self._get_current_user()
        params = V()._api_validation(self._get_params(), pd_schema)
        name, size = params['name'], params['size']

        pd = PersistentDisk.query.filter_by(name=name).first()
        if pd is not None:
            raise APIError('{0} already exists'.format(name), 406,
                           type='DuplicateName')
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
        return add_kube_types(data)

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


def add_kube_types(disks):
    if not isinstance(disks, Sequence):  # one disk
        node_id = disks.get('node_id')
        if node_id is not None:
            disks['kube_type'] = Node.query.get(node_id).kube_id
        return disks
    node2kube = dict(Node.query.values(Node.id, Node.kube_id))
    for disk in disks:
        disk['kube_type'] = node2kube.get(disk.get('node_id'))
    return disks


register_api(pstorage, PersistentStorageAPI, 'pstorage', '/', 'device_id',
             strict_slashes=False)
