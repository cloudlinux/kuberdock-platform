from functools import wraps

from flask import Blueprint, Response, jsonify, request
from flask.views import MethodView

from kubedock.api.utils import use_kwargs
from kubedock.validation import extbool
from ..decorators import maintenance_protected
from ..exceptions import APIError
from ..kapi.apps import PredefinedApp
from ..login import auth_required
from ..rbac import check_permission
from ..utils import KubeUtils, register_api

predefined_apps = Blueprint('predefined_apps', __name__,
                            url_prefix='/predefined-apps')

create_params_schema = {
    'name': {'type': 'string', 'required': True, 'nullable': False,
             'empty': False},
    'template': {'type': 'string',
                 'required': False,  # can be uploaded as file
                 'nullable': True},
    'origin': {'type': 'string', 'required': False, 'nullable': True},
    'validate': {'type': 'boolean', 'required': False, 'nullable': True,
                 'coerce': extbool}
}

edit_params_schema = {
    'name': {'type': 'string', 'required': False, 'nullable': True},
    'template': {'type': 'string', 'required': False, 'nullable': True},
    'validate': {'type': 'boolean', 'required': False, 'nullable': True,
                 'coerce': extbool}
}


def _take_template_from_uploads_if_needed(fn):
    """Takes template from request.files if 'template' from **kwargs is empty.
    Must be after @use_kwargs.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        template = kwargs.get('template')
        if template is None:
            template = request.files.to_dict().get('template')
            if template is not None:
                template = template.stream.read()
        kwargs['template'] = template
        return fn(*args, **kwargs)

    return wrapper


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
    @use_kwargs(create_params_schema)
    @_take_template_from_uploads_if_needed
    def post(self, name, template, origin=None, validate=False):
        if template is None:
            raise APIError('template not provided')
        if validate:
            PredefinedApp.validate(template)  # OK if no exception
        app = PredefinedApp.create(name=name, template=template, origin=origin)
        return app.to_dict()

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('edit', 'predefined_apps')
    @use_kwargs(edit_params_schema)
    @_take_template_from_uploads_if_needed
    def put(self, app_id, template=None, validate=False, **params):
        if validate and template is not None:
            PredefinedApp.validate(template)  # OK if no exception
        params.update(template=template)
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
@use_kwargs({'template': {'type': 'string', 'required': False,
                          'nullable': True}})
@_take_template_from_uploads_if_needed
def validate_template(template):
    if not template:
        raise APIError('Empty template')
    PredefinedApp.validate(template)    # OK if no exception
