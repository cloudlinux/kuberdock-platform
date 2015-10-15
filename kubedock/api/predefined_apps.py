from flask import Blueprint, Response, jsonify, request
from flask.views import MethodView
from ..utils import (login_required_or_basic_or_token, KubeUtils, register_api,
                     maintenance_protected, APIError)
from ..kapi.predefined_apps import PredefinedApps


predefined_apps = Blueprint('predefined_apps', __name__,
                            url_prefix='/predefined-apps')


class PredefinedAppsAPI(KubeUtils, MethodView):
    decorators = [login_required_or_basic_or_token]

    def get(self, app_id=None):
        user = self._get_current_user()
        if user.is_administrator():
            app = PredefinedApps().get(app_id)
        else:
            app = PredefinedApps(user).get(app_id)

        file_only = self._get_params().get('file-only', False)
        if app_id is not None and file_only:
            return Response(app['template'], content_type='application/x-yaml')
        return jsonify({'status': 'OK', 'data': app})

    @KubeUtils.jsonwrap
    @maintenance_protected
    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        name = params.get('name')
        if name is None:
            raise APIError('template name not provided')
        template = params.get('template')
        if template is None:
            template = request.files.to_dict().get('template')
            if template is None:
                raise APIError('template not provided')
            template = template.stream.read()
        return PredefinedApps(user).create(name=name, template=template)

    @KubeUtils.jsonwrap
    @maintenance_protected
    def put(self, app_id):
        user = self._get_current_user()
        params = self._get_params()
        name = params.get('name')
        template = params.get('template')

        return PredefinedApps(user).update(app_id, name=name, template=template)

    @KubeUtils.jsonwrap
    @maintenance_protected
    def delete(self, app_id):
        user = self._get_current_user()
        return PredefinedApps(user).delete(app_id)

register_api(predefined_apps, PredefinedAppsAPI, 'predefined_apps', '/',
             'app_id', strict_slashes=False)
