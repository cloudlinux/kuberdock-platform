import yaml
from flask import Blueprint, Response
from flask.views import MethodView

from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError, PredefinedAppExc, InsufficientData
from kubedock.login import auth_required
from kubedock.utils import KubeUtils, register_api, send_event_to_user
from kubedock.kapi.podcollection import PodCollection
from kubedock.validation import check_new_pod_data
from kubedock.rbac import check_permission
from kubedock.kapi.apps import PredefinedApp, dispatch_kind
from kubedock.validation.coerce import extbool


yamlapi = Blueprint('yaml_api', __name__, url_prefix='/yamlapi')


class YamlAPI(KubeUtils, MethodView):
    decorators = (
        KubeUtils.jsonwrap,
        check_permission('create', 'yaml_pods'),
        KubeUtils.pod_start_permissions,
        auth_required
    )

    @maintenance_protected
    def post(self):
        user = self.get_current_user()
        data = self._get_params().get('data')
        if data is None:
            raise InsufficientData('No "data" provided')
        try:
            parsed_data = list(yaml.safe_load_all(data))
        except yaml.YAMLError as e:
            raise PredefinedAppExc.UnparseableTemplate(
                'Incorrect yaml, parsing failed: "{0}"'.format(str(e)))
        new_pod = dispatch_kind(parsed_data)
        new_pod = check_new_pod_data(new_pod, user)

        if user.role.rolename == 'LimitedUser':
            template_id = new_pod.get('kuberdock_template_id')
            if template_id is None:
                raise PredefinedAppExc.NotPredefinedAppPod
            pa = PredefinedApp.get(template_id)
            if not pa.is_template_for(parsed_data[0]):
                raise PredefinedAppExc.NotPredefinedAppPod

        try:
            res = PodCollection(user).add(new_pod)
        except APIError as e:  # pass as is
            raise
        except Exception as e:
            raise PredefinedAppExc.InternalPredefinedAppError(
                details={'message': str(e)})
        send_event_to_user('pod:change', res, user.id)
        return res

register_api(yamlapi, YamlAPI, 'yamlapi', '/', 'pod_id', strict_slashes=False)


@yamlapi.route('/fill/<int:template_id>/<int:plan_id>', methods=['POST'])
def fill_template(template_id, plan_id):
    data = KubeUtils._get_params()
    app = PredefinedApp.get(template_id)
    filled = app.get_filled_template_for_plan(plan_id, data, as_yaml=True)
    return Response(filled, content_type='application/x-yaml')


@yamlapi.route('/create/<int:template_id>/<int:plan_id>', methods=['POST'])
@auth_required
@check_permission('create', 'yaml_pods')
@KubeUtils.jsonwrap
def create_pod(template_id, plan_id):
    user = KubeUtils.get_current_user()
    data = KubeUtils._get_params()
    start = extbool(data.pop('start', True))
    app = PredefinedApp.get(template_id)
    pod_data = app.get_filled_template_for_plan(plan_id, data, user=user)
    new_pod = dispatch_kind([pod_data], template_id)
    new_pod = check_new_pod_data(new_pod, user)
    res = PodCollection(user).add(new_pod)
    if start:
        PodCollection(user).update(res['id'],
                                   {'command': 'start', 'commandOptions': {}})
    return res


@yamlapi.route('/switch/<pod_id>/<plan_id>', methods=['PUT'])
@auth_required
@KubeUtils.jsonwrap
def switch_pod_plan(pod_id, plan_id):
    params = KubeUtils._get_params()
    async = params.get('async') != 'false'
    current_user = KubeUtils.get_current_user()
    if plan_id.isdigit():   # plan_id specified with index (e.g. 0)
        plan_id = int(plan_id)
        func = PredefinedApp.update_pod_to_plan
    else:  # plan_id specified with name ('M', 'XXL')
        func = PredefinedApp.update_pod_to_plan_by_name
    return func(pod_id, plan_id, async=async, user=current_user)
