from flask import Blueprint, Response, jsonify, request
from flask.views import MethodView
from ..decorators import maintenance_protected
from ..exceptions import APIError
from ..login import auth_required
from ..utils import KubeUtils, register_api, all_request_params
from ..kapi.apps import PredefinedApp
from ..rbac import check_permission


predefined_apps = Blueprint('predefined_apps', __name__,
                            url_prefix='/predefined-apps')


class PredefinedAppsAPI(KubeUtils, MethodView):
    decorators = [auth_required]

    @check_permission('get', 'predefined_apps')
    def get(self, app_id=None):
        if app_id is None:
            return jsonify({'status': 'OK',
                            'data': PredefinedApp.all(as_dict=True)})
        file_only = self._get_params().get('file-only', False)
        app = PredefinedApp.get(app_id)
        if file_only:
            return Response(app.template, content_type='application/x-yaml')
        return jsonify({'status': 'OK', 'data': app.to_dict()})

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('create', 'predefined_apps')
    def post(self):
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
        if validate:
            PredefinedApp.validate(template)    # OK if no exception
        app = PredefinedApp.create(name=name, template=template, origin=origin)
        return app.to_dict()

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('edit', 'predefined_apps')
    def put(self, app_id):
        params = self._get_params()
        validate = params.pop('validate', False)
        if validate and 'template' in params:
            PredefinedApp.validate(params['template'])  # OK if no exception
        params.pop('id', None)
        app = PredefinedApp.update(app_id, **params)
        return app.to_dict()

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('delete', 'predefined_apps')
    def delete(self, app_id):
        PredefinedApp.delete(app_id)

register_api(predefined_apps, PredefinedAppsAPI, 'predefined_apps', '/',
             'app_id', strict_slashes=False)


@predefined_apps.route('/validate-template', methods=['POST'],
                       strict_slashes=False)
@auth_required
@check_permission('create', 'predefined_apps')
@KubeUtils.jsonwrap
def validate_template():
    params = all_request_params()
    template = params.get('template')
    if not template:
        raise APIError('Empty template')
    PredefinedApp.validate(template)    # OK if no exception
