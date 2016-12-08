import yaml
from flask import Blueprint, Response, jsonify
from flask.views import MethodView

from kubedock.api.utils import use_kwargs
from kubedock.billing import has_billing
from kubedock.decorators import maintenance_protected
from kubedock.exceptions import (
    APIError, InsufficientData, PermissionDenied, PredefinedAppExc, NoFreeIPs,
    NoFreeIPsAdminNotification)
from kubedock.kapi.apps import PredefinedApp, AppInstance, start_pod_from_yaml
from kubedock.kapi.podcollection import PodCollection
from kubedock.login import auth_required
from kubedock.rbac import check_permission
from kubedock.utils import KubeUtils, register_api, send_event_to_user
from kubedock.validation.coerce import extbool
from kubedock.validation.schemas import owner_optional_schema, boolean

yamlapi = Blueprint('yaml_api', __name__, url_prefix='/yamlapi')


def check_owner(owner=None):
    current_user = KubeUtils.get_current_user()
    owner = owner or current_user

    check_permission('own', 'pods', user=owner).check()
    if owner == current_user:
        check_permission('create', 'yaml_pods').check()
    else:
        check_permission('create_non_owned', 'yaml_pods').check()
    return owner


class YamlAPI(KubeUtils, MethodView):
    decorators = (
        KubeUtils.jsonwrap,
        check_permission('create', 'yaml_pods'),
        KubeUtils.pod_start_permissions,
        auth_required
    )

    @maintenance_protected
    @use_kwargs({'data': {'type': 'string', 'empty': False}},
                allow_unknown=True)
    def post(self, **params):
        user = self.get_current_user()
        data = params.get('data')
        if data is None:
            raise InsufficientData('No "data" provided')
        try:
            parsed_data = list(yaml.safe_load_all(data))
        except yaml.YAMLError as e:
            raise PredefinedAppExc.UnparseableTemplate(
                'Incorrect yaml, parsing failed: "{0}"'.format(str(e)))

        try:
            res = start_pod_from_yaml(parsed_data, user=user)
        except APIError as e:  # pass as is
            raise
        except Exception as e:
            raise PredefinedAppExc.InternalPredefinedAppError(
                details={'message': str(e)})
        send_event_to_user('pod:change', res, user.id)
        return res


register_api(yamlapi, YamlAPI, 'yamlapi', '/', 'pod_id')


@yamlapi.route('/fill/<int:template_id>/<int:plan_id>', methods=['POST'])
@use_kwargs({'raw': boolean},
            allow_unknown=True)
@auth_required
def fill_template(template_id, plan_id, raw=False, **params):
    app = PredefinedApp.get(template_id)
    filled = app.get_filled_template_for_plan(plan_id, params, as_yaml=True)
    if raw:
        return Response(filled, content_type='application/x-yaml')
    else:
        return jsonify({'status': 'OK', 'data': filled})


# TODO Apps API instead of "/create/", "/switch/", and "/update/":
#     GET /apps/<app-id>/ - return list of pods (with only one pod, for now),
#       template id, plan id, version id, app variables, is update available,
#       is switching allowed, postDescriotion,..
#     POST /apps/ - {templateID, planID, [appVariables,] [start,] [owner,]} ->
#       instead of "/create/"
#     PUT /apps/<app-id>/ - {versionID or planID} for update or switching plan
#     DELETE /apps/<app-id>/ - delete all pods (only one pod, for now)
# for now, app_id may be equal to pod_id.
# apps = Blueprint('apps_api', __name__, url_prefix='/apps')


@yamlapi.route('/create/<int:template_id>/<int:plan_id>', methods=['POST'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs({'owner': owner_optional_schema,
             'start': {'type': 'boolean', 'coerce': extbool}},
            allow_unknown=True)
def create_pod(template_id, plan_id, owner=None, start=True, **data):
    owner = check_owner(owner)

    app = PredefinedApp.get(template_id)

    if not owner.is_administrator() and has_billing() and owner.fix_price:
        raise PermissionDenied
    pod_data = app.get_filled_template_for_plan(plan_id, data)
    try:
        res = start_pod_from_yaml(pod_data, user=owner,
                                  template_id=template_id)
    except NoFreeIPs:
        raise NoFreeIPsAdminNotification

    if start:
        PodCollection(owner).update(
            res['id'], {'command': 'start', 'commandOptions': {}})
    return res


@yamlapi.route('/switch/<pod_id>/<plan_id>', methods=['PUT'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs({'async': {'type': 'boolean', 'coerce': extbool},
             'dry-run': {'type': 'boolean', 'coerce': extbool}},
            allow_unknown=True)
def switch_pod_plan(pod_id, plan_id, **params):
    async = params.get('async', True)
    dry_run = params.get('dry-run', False)
    current_user = KubeUtils.get_current_user()
    app = AppInstance(pod_id, current_user)
    if plan_id.isdigit():  # plan_id specified with index (e.g. 0)
        plan_id = int(plan_id)
        func = app.update_plan
    else:  # plan_id specified with name ('M', 'XXL')
        func = app.update_plan_by_name
    return func(plan_id, async=async, dry_run=dry_run)


@yamlapi.route('/update/<pod_id>', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs({'owner': owner_optional_schema}, allow_unknown=True)
def check_for_updates(pod_id, owner=None, **_):
    check_owner(owner)
    return AppInstance(pod_id).check_for_updates()


@yamlapi.route('/update/<pod_id>', methods=['POST'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs({'owner': owner_optional_schema}, allow_unknown=True)
def update(pod_id, owner=None, **_):
    check_owner(owner)
    return AppInstance(pod_id).update_version()
