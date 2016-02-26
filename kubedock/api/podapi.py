from flask import Blueprint
from flask.views import MethodView
from ..decorators import login_required_or_basic_or_token
from ..decorators import maintenance_protected
from ..utils import KubeUtils, register_api
from ..kapi.podcollection import PodCollection
from ..validation import check_new_pod_data, V, update_pod_schema
from ..rbac import check_permission


podapi = Blueprint('podapi', __name__, url_prefix='/podapi')


class PodsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, check_permission('get', 'pods'),
                  KubeUtils.pod_start_permissions, login_required_or_basic_or_token]

    def get(self, pod_id):
        #params = self._get_params()
        user = self._get_current_user()
        return PodCollection(user).get(pod_id, as_json=False)

    @maintenance_protected
    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        check_new_pod_data(params, user)
        return PodCollection(user).add(params)

    @maintenance_protected
    def put(self, pod_id):
        user = self._get_current_user()
        params = self._get_params()
        #check_change_pod_data(params)
        params = V(allow_unknown=True)._api_validation(params, update_pod_schema)
        # TODO: with cerberus 0.10, just use "purge_unknown" option
        data = {'command': params.get('command'),
                'commandOptions': params.get('commandOptions') or {}}
        pods = PodCollection(user)
        return pods.update(pod_id, data)
    patch = put

    @maintenance_protected
    def delete(self, pod_id):
        user = self._get_current_user()
        pods = PodCollection(user)
        return pods.delete(pod_id)
register_api(podapi, PodsAPI, 'podapi', '/', 'pod_id', strict_slashes=False)


@podapi.route('/<pod_id>/<container_name>/update', methods=['GET'],
              strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'pods')
def check_updates(pod_id, container_name):
    user = KubeUtils._get_current_user()
    return PodCollection(user).check_updates(pod_id, container_name)


@podapi.route('/<pod_id>/<container_name>/update', methods=['POST'],
              strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'pods')
def update_container(pod_id, container_name):
    user = KubeUtils._get_current_user()
    return PodCollection(user).update_container(pod_id, container_name)
