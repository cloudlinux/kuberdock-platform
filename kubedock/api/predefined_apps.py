from flask import Blueprint, Response, jsonify, request
from flask.views import MethodView
from ..decorators import (login_required_or_basic_or_token,
                          maintenance_protected)
from ..utils import KubeUtils, register_api, APIError, all_request_params
from ..kapi import predefined_apps as kapi_apps
from ..rbac import check_permission


predefined_apps = Blueprint('predefined_apps', __name__,
                            url_prefix='/predefined-apps')


class PredefinedAppsAPI(KubeUtils, MethodView):
    decorators = [login_required_or_basic_or_token]

    @check_permission('get', 'predefined_apps')
    def get(self, app_id=None):
        app = kapi_apps.PredefinedApps().get(app_id)

        file_only = self._get_params().get('file-only', False)
        if app_id is not None and file_only:
            return Response(app['template'], content_type='application/x-yaml')
        return jsonify({'status': 'OK', 'data': app})

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('create', 'predefined_apps')
    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        name = params.get('name')
        origin = params.get('origin')
        validate = params.get('validate') or False
        if name is None:
            raise APIError('template name not provided')
        template = params.get('template')
        if template is None:
            template = request.files.to_dict().get('template')
            if template is None:
                raise APIError('template not provided')
            template = template.stream.read()
        return kapi_apps.PredefinedApps(user).create(name=name,
                                                     template=template,
                                                     origin=origin,
                                                     validate=validate)

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('edit', 'predefined_apps')
    def put(self, app_id):
        user = self._get_current_user()
        params = self._get_params()
        name = params.get('name')
        template = params.get('template')
        validate = params.get('validate') or False

        return kapi_apps.PredefinedApps(user).update(
            app_id, name=name, template=template, validate=validate)

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('delete', 'predefined_apps')
    def delete(self, app_id):
        user = self._get_current_user()
        return kapi_apps.PredefinedApps(user).delete(app_id)

register_api(predefined_apps, PredefinedAppsAPI, 'predefined_apps', '/',
             'app_id', strict_slashes=False)


@predefined_apps.route('/validate-template', methods=['POST'],
                       endpoint='validate_template', strict_slashes=False)
@KubeUtils.jsonwrap
def validate_template():
    params = all_request_params()
    template = params.get('template')
    if not template:
        raise APIError('Empty template')
    kapi_apps.validate_template(template)
    return {}
