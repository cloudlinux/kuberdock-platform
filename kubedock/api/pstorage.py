from flask import Blueprint
from flask.views import MethodView

from ..utils import login_required_or_basic_or_token, KubeUtils, register_api
from ..kapi import pstorage as ps
from ..settings import AWS, CEPH


pstorage = Blueprint('pstorage', __name__, url_prefix='/pstorage')


class PersistentStorageAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, KubeUtils.pod_permissions, login_required_or_basic_or_token]

    @staticmethod
    def _resolve_storage():
        if CEPH:
            return ps.CephStorage
        if AWS:
            return ps.AmazonStorage
        return ps.PersistentStorage

    def get(self, device_id):
        #params = self._get_params()
        user = self._get_current_user()
        cls = self._resolve_storage()
        return cls().get_by_user(user, device_id)

    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        cls = self._resolve_storage()
        return cls().create(params['name'], params['size'], user)

    def put(self, device_id):
        pass

    def delete(self, device_id):
        cls = self._resolve_storage()
        return cls().delete_by_id(device_id)

register_api(pstorage, PersistentStorageAPI, 'pstorage', '/', 'device_id', strict_slashes=False)