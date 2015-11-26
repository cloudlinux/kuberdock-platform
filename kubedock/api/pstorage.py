from flask import Blueprint
from flask.views import MethodView

from . import APIError
from ..decorators import login_required_or_basic_or_token
from ..utils import KubeUtils, register_api
from ..kapi import pstorage as ps
from ..pods.models import PersistentDisk


pstorage = Blueprint('pstorage', __name__, url_prefix='/pstorage')


class PersistentStorageAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, KubeUtils.pod_permissions, login_required_or_basic_or_token]

    @staticmethod
    def _resolve_storage():
        storage_cls = ps.get_storage_class()
        return storage_cls or ps.PersistentStorage

    def get(self, device_id):
        params = self._get_params()
        user = self._get_current_user()
        cls = self._resolve_storage()
        if params.get('free-only') == 'true':
            return cls().get_user_unmapped_drives(user)
        return cls().get_by_user(user, device_id)

    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        pd = PersistentDisk(size=params['size'], owner=user, name=params['name'])

        Storage = self._resolve_storage()
        data = Storage().create(pd)
        if data is None:
            raise APIError('Couldn\'t create drive.')
        try:
            pd.save()
        except Exception:
            Storage().delete_by_id(data['id'])
            raise APIError('Couldn\'t save persistent disk.')
        return data

    def put(self, device_id):
        pass

    def delete(self, device_id):
        cls = self._resolve_storage()
        result = cls().delete_by_id(device_id)
        try:
            PersistentDisk.query.filter_by(id=device_id).delete()
        except Exception:
            raise APIError('Couldn\'t delete persistent disk.')
        return result

register_api(pstorage, PersistentStorageAPI, 'pstorage', '/', 'device_id', strict_slashes=False)
