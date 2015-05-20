from flask import Blueprint, request, Response
from flask.views import MethodView
from ..utils import login_required_or_basic, KubeUtils, register_api
from ..kapi.podcollection import PodCollection, DriveCollection
from ..kapi.pod import Pod
from ..validation import check_new_pod_data


podapi = Blueprint('podapi', __name__, url_prefix='/podapi')


class PodsAPI(KubeUtils, MethodView):
    decorators = [login_required_or_basic, KubeUtils.pod_permissions, KubeUtils.jsonwrap]

    def get(self, pod_id):
        #params = self._get_params()
        user = self._get_current_user()
        data = [p.as_dict() for p in PodCollection().get_by_username(user.username)]
        return data

    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        check_new_pod_data(params)
        pod = Pod.create(params, user)
        return pod.save()

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


@podapi.route('/pd/<string:kub_id>', methods=['GET'])
def lookup_pd(kub_id):
    """
    Return persistent drives list as text to a node
    :param kub_id: string UUID -> internal kubernetes pod ID
    """
    remote_addr = request.environ['REMOTE_ADDR']
    return Response(
        DriveCollection().get_drives_for_node(remote_addr, kub_id),
        mimetype="text/plain")
