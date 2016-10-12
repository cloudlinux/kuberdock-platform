from collections import Sequence

from flask import Blueprint
from flask.views import MethodView

from kubedock.api.utils import use_kwargs
from ..exceptions import APIError, PDNotFound
from ..kapi import pstorage as ps
from ..login import auth_required
from ..nodes.models import Node
from ..pods.models import PersistentDisk
from ..rbac import check_permission
from ..utils import KubeUtils, register_api
from ..validation.schemas import pd_schema, owner_optional_schema
from kubedock.kapi.pstorage import STORAGE_CLASS
from kubedock.kapi import podcollection

pstorage = Blueprint('pstorage', __name__, url_prefix='/pstorage')


class PDIsUsed(APIError):
    message = 'Persistent disk is used.'


schema_with_owner = {
    'owner': owner_optional_schema
}

schema_with_owner_and_data = dict(owner=owner_optional_schema, **pd_schema)


class PersistentStorageAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, auth_required]

    @staticmethod
    def _resolve_storage():
        return STORAGE_CLASS or ps.PersistentStorage

    @use_kwargs(schema_with_owner, allow_unknown=True)
    def get(self, device_id, owner=None, **params):
        current_user = self.get_current_user()
        owner = owner or current_user

        check_permission('own', 'persistent_volumes', user=owner).check()
        if owner == current_user:
            check_permission('get', 'persistent_volumes').check()
        else:
            check_permission('get_non_owned', 'persistent_volumes').check()

        cls = self._resolve_storage()
        free_only = params.get('free-only')
        if free_only == 'true' or free_only is True:
            return add_kube_types(cls().get_user_unmapped_drives(owner))
        if device_id is None:
            return add_kube_types(cls().get_by_user(owner))
        disks = cls().get_by_user(owner, device_id)
        if not disks:
            raise PDNotFound()
        return add_kube_types(disks)

    @use_kwargs(schema_with_owner_and_data)
    def post(self, owner=None, **params):
        current_user = self.get_current_user()
        owner = owner or current_user

        check_permission('own', 'persistent_volumes', user=owner).check()
        if owner == current_user:
            check_permission('create', 'persistent_volumes').check()
        else:
            check_permission('create_non_owned', 'persistent_volumes').check()

        name, size = params['name'], params['size']

        pd = PersistentDisk.query.filter_by(name=name).first()
        if pd is not None:
            raise APIError('{0} already exists'.format(name), 406,
                           type='DuplicateName')
        pd = PersistentDisk(size=size, owner=owner, name=name)
        storage_cls = self._resolve_storage()
        data = storage_cls().create(pd)
        if data is None:
            raise APIError('Couldn\'t create drive.')
        try:
            pd.save()
        except Exception:
            ps.delete_drive_by_id(data['id'])
            raise APIError('Couldn\'t save persistent disk.')
        return add_kube_types(data)

    @use_kwargs(schema_with_owner_and_data)
    def put(self, device_id, owner=None, **params):
        current_user = self.get_current_user()
        owner = owner or current_user

        check_permission('own', 'persistent_volumes', user=owner).check()
        if owner == current_user:
            check_permission('edit', 'persistent_volumes').check()
        else:
            check_permission('edit_non_owned', 'persistent_volumes').check()

        size = params['size']
        return podcollection.change_pv_size(device_id, int(size))

    @use_kwargs(schema_with_owner)
    def delete(self, device_id, owner=None):
        current_user = self.get_current_user()
        owner = owner or current_user

        check_permission('own', 'persistent_volumes', user=owner).check()
        if owner == current_user:
            check_permission('delete', 'persistent_volumes').check()
        else:
            check_permission('delete_non_owned', 'persistent_volumes').check()

        pd = PersistentDisk.get_all_query().filter(
            PersistentDisk.id == device_id,
            # allow deletion owner's PDs only
            PersistentDisk.owner_id == owner.id
        ).first()
        if pd is None:
            raise PDNotFound()
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


register_api(pstorage, PersistentStorageAPI, 'pstorage', '/', 'device_id')


@pstorage.route('/is_volume_resizable', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def is_volume_resizable():
    return STORAGE_CLASS().is_pv_resizable()
