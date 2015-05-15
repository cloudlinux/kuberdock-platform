from flask import Blueprint, request, current_app, jsonify, g
from flask.views import MethodView
from ..utils import login_required_or_basic, KubeUtils, register_api
from ..kapi.podcollection import PodCollection
from ..kapi.pod import Pod
from ..validation import check_new_pod_data, check_change_pod_data
from .namespaces import Namespaces, NamespacesPods

podapi = Blueprint('podapi', __name__, url_prefix='/podapi')


class PodsAPI(KubeUtils, MethodView):
    decorators = [login_required_or_basic, KubeUtils.pod_permissions, KubeUtils.jsonwrap]
    
    def get(self, pod_id):
        user = self._get_current_user()
        data = [p.as_dict() for p in PodCollection().get_by_username(user.username)]
        return data
    
    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        check_new_pod_data(params)
        pod = Pod.create(params)
        return pod.save(user)
    
    def put(self, pod_id):
        params = self._get_params()
        #check_change_pod_data(params)
        pods = PodCollection()
        pod = pods.get_by_id(pod_id)
        pods.update(pod, params)
    
    def delete(self, pod_id):
        pods = PodCollection()
        pod = pods.get_by_id(pod_id)
        pods.delete(pod)

register_api(podapi, PodsAPI, 'podapi', '/', 'pod_id')