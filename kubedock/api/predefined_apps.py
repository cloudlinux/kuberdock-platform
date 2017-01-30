
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

from functools import wraps

from flask import Blueprint, Response, jsonify, request
from flask.views import MethodView

from kubedock.api.utils import use_kwargs
from kubedock.validation import extbool, V, boolean
from ..decorators import maintenance_protected
from ..exceptions import APIError, PredefinedAppExc, PermissionDenied
from ..kapi.apps import PredefinedApp
from ..login import auth_required
from ..rbac import check_permission
from ..utils import KubeUtils, register_api
from kubedock.predefined_apps.models import PredefinedApp as PredefinedAppModel

predefined_apps = Blueprint('predefined_apps', __name__,
                            url_prefix='/predefined-apps')

create_params_schema = {
    'name': {'type': 'string', 'required': True, 'empty': False},
    'icon': {'type': 'string', 'required': False, 'nullable': True,
             'icon': True},
    'template': {'type': 'string', 'required': True, 'nullable': True},
    'origin': {'type': 'string', 'nullable': True},
    'validate': {'type': 'boolean', 'nullable': True, 'coerce': extbool},
    'switchingPackagesAllowed': {'type': 'boolean',
                                 'nullable': True, 'coerce': extbool},
    'search_available': {'type': 'boolean', 'coerce': extbool,
                         'nullable': True},
}

create_version_params_schema = {
    'template': {'type': 'string', 'required': True, 'nullable': True},
    'validate': {'type': 'boolean', 'nullable': True, 'coerce': extbool},
    'active': {'type': 'boolean', 'nullable': True, 'coerce': extbool},
    'switchingPackagesAllowed': {'type': 'boolean',
                                 'nullable': True, 'coerce': extbool}
}

edit_params_schema = {
    'name': {'type': 'string', 'required': False, 'nullable': True},
    'icon': {'type': 'string', 'required': False, 'nullable': True,
             'icon': True},
    'template': {'type': 'string', 'required': False, 'nullable': True},
    'validate': {'type': 'boolean', 'required': False, 'nullable': True,
                 'coerce': extbool},
    'active': {'type': 'boolean', 'required': False, 'nullable': True,
               'coerce': extbool},
    'switchingPackagesAllowed': {'type': 'boolean', 'required': False,
                                 'nullable': True, 'coerce': extbool},
    'search_available': boolean,
}


def _take_template_from_uploads_if_needed(fn):
    """Takes template from request.files if 'template' from **kwargs is empty.
    Must be called before @use_kwargs.
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


def _purged_unknown(params, schema):
    """Purge unknown params and params with not set values"""
    params = {param: value for param, value in params.items()
              if param in schema}
    return params


class PredefinedAppsAPI(KubeUtils, MethodView):
    decorators = [auth_required]

    @check_permission('get', 'predefined_apps')
    @use_kwargs({'with-plans': {'type': 'boolean', 'coerce': extbool},
                 'with-entities': {'type': 'boolean', 'coerce': extbool},
                 'file-only': {'type': 'boolean', 'coerce': extbool},
                 'searchkey': {'type': 'string', 'required': False}
                 },

                allow_unknown=True)
    def get(self, app_id=None, version_id=None, **params):
        get_unavailable = bool(check_permission('get_unavailable',
                                           'predefined_apps'))

        if app_id is None:
            query_filter = []
            if not get_unavailable:
                query_filter.append(
                    PredefinedAppModel.search_available.is_(True))
            searchkey = params.get('searchkey')
            if searchkey:
                query_filter.append(
                    PredefinedAppModel.name.ilike('%{}%'.format(searchkey)))
            return jsonify({'status': 'OK',
                            'data': PredefinedApp.all(as_dict=True,
                                                      query_filter=query_filter
                                                      )})

        app = PredefinedApp.get(app_id, version_id)
        if not get_unavailable and not app.search_available:
            raise PermissionDenied

        if params.get('file-only'):
            return Response(app.template, content_type='application/x-yaml')
        response_dict = {
            'status': 'OK',
            'data': app.to_dict(
                with_plans=params.get('with-plans'),
                with_entities=params.get('with-entities')
            )
        }
        if version_id is None:
            response_dict['data']['templates'] = app.templates

        return jsonify(response_dict)

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('create', 'predefined_apps')
    @_take_template_from_uploads_if_needed
    def post(self, app_id=None, template=None):
        params = self._get_params()
        if template:
            params['template'] = template

        schema = create_params_schema
        if app_id is not None:
            schema = create_version_params_schema
        params = V(allow_unknown=True)._api_validation(params, schema)
        # TODO: with cerberus 1.0 use purge_unknown
        params = {key: val for key, val in params.items() if key in schema}

        if params.pop('validate', None):
            PredefinedApp.validate(params['template'])  # OK if no exception
        if app_id:
            app = PredefinedApp.update(app_id, new_version=True, **params)
        else:
            app = PredefinedApp.create(**params)
        return dict(app.to_dict(), templates=app.templates)

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('edit', 'predefined_apps')
    @use_kwargs(edit_params_schema, allow_unknown=True)
    @_take_template_from_uploads_if_needed
    def put(self, app_id, version_id=None, template=None,
            validate=False, **params):
        if validate and template is not None:
            PredefinedApp.validate(template)  # OK if no exception
        # TODO: with cerberus 1.0 use purge_unknown
        params = _purged_unknown(params, edit_params_schema)
        params.update(template=template)
        app = PredefinedApp.update(app_id, version_id=version_id, **params)
        if not app:
            raise PredefinedAppExc.NoSuchPredefinedApp
        return dict(app.to_dict(), templates=app.templates)

    @KubeUtils.jsonwrap
    @maintenance_protected
    @check_permission('delete', 'predefined_apps')
    def delete(self, app_id, version_id=None):
        PredefinedApp.delete(app_id, version_id)


# predefined application api
register_api(predefined_apps, PredefinedAppsAPI, 'predefined_apps', '/',
             'app_id', pk_type='int')

# versions api
register_api(predefined_apps, PredefinedAppsAPI, 'predefined_apps_versions',
             '/<int:app_id>/', 'version_id', pk_type='int')


@predefined_apps.route('/validate-template/<int:app_id>', methods=['POST'])
@predefined_apps.route('/validate-template', methods=['POST'])
@auth_required
@check_permission('create', 'predefined_apps')
@KubeUtils.jsonwrap
@use_kwargs({'template': {'type': 'string', 'required': False,
                          'nullable': True}})
@_take_template_from_uploads_if_needed
def validate_template(template):
    if not template:
        raise APIError('Empty template')
    PredefinedApp.validate(template)  # OK if no exception
