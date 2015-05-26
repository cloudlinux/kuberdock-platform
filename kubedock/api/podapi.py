from flask import Blueprint
from flask.views import MethodView
from ..utils import login_required_or_basic, KubeUtils, register_api
from ..kapi.podcollection import PodCollection
from ..validation import check_new_pod_data


podapi = Blueprint('podapi', __name__, url_prefix='/podapi')


class PodsAPI(KubeUtils, MethodView):
    decorators = [login_required_or_basic, KubeUtils.pod_permissions, KubeUtils.jsonwrap]

    def get(self, pod_id):
        #params = self._get_params()
        user = self._get_current_user()
        return PodCollection(user).get(as_json=False)

    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        check_new_pod_data(params)
        return PodCollection(user).add(params)

    def put(self, pod_id):
        user = self._get_current_user()
        params = self._get_params()
        #check_change_pod_data(params)
        pods = PodCollection(user)
        return pods.update(pod_id, params)

    def delete(self, pod_id):
        user = self._get_current_user()
        pods = PodCollection(user)
        return pods.delete(pod_id)
register_api(podapi, PodsAPI, 'podapi', '/', 'pod_id')
