from pytz import common_timezones, timezone
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask.ext.login import current_user
from flask.views import MethodView

from ..rbac import check_permission
from ..decorators import login_required_or_basic_or_token
from ..exceptions import PermissionDenied
from ..utils import KubeUtils, register_api
from ..users.utils import append_offset_to_timezone
from ..kapi.notifications import read_role_events
from ..static_pages.models import MenuItem
from ..system_settings.models import SystemSettings
from ..validation import check_system_settings

settings = Blueprint('settings', __name__, url_prefix='/settings')


# @check_permission("get_permissions", "settings")
# def get_permissions():
#     data = []
#     roles = {r.id: r.to_dict() for r in Role.all()}
#     for res in Resource.all():
#         perms = set()
#         _roles = {}
#         for p in res.permissions:
#             perms.add(p.name)
#             role = roles[p.role_id]
#             rolename = role['rolename']
#             if rolename in _roles:
#                 _roles[rolename].append(p.to_dict())
#             else:
#                 _roles[rolename] = [p.to_dict()]
#         data.append({'id': res.id, 'name': res.name,
#                       'permissions': list(perms),
#                      'roles': _roles, 'all_roles': roles})
#     return roles, data
#
#
# @settings.route('/permissions/<pid>', methods=['PUT'])
# @login_required_or_basic_or_token
# @check_permission("set_permissions", "settings")
# def permissions(pid):
#     data = request.json or request.form.to_dict()
#     allow = data.get('allow')
#     if allow not in ('true', 'false', True, False):
#         raise APIError("Value error: {0}".format(allow))
#     perm = Permission.query.get(int(pid))
#     if allow in ('true', True):
#         perm.set_allow()
#     else:
#         perm.set_deny()
#     acl.init_permissions()
#     return jsonify({'status': 'OK'})


def enrich_with_plugin_list(data):
    plugins = ['No billing'] + \
        current_app.billing_factory.list_billing_plugins()
    if isinstance(data, list):
        rv = [i for i in data if i.get('name') == 'billing_type']
        if rv:
            rv[0]['options'] = plugins
    elif isinstance(data, dict):
        if data.get('name') == 'billing_type':
            data['options'] = plugins
    return data


@settings.route('/notifications', methods=['GET'])
@login_required_or_basic_or_token
@KubeUtils.jsonwrap
def get_notifications():
    return read_role_events(KubeUtils._get_current_user().role)


@settings.route('/menu', methods=['GET'])
@login_required_or_basic_or_token
@KubeUtils.jsonwrap
def get_menu():
    return MenuItem.get_menu()


@settings.route('/timezone', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'timezone')
def get_timezone():
    search_result_length = 5
    search = request.args.get('s', '')
    search = search.lower()
    count = 0
    timezones_list = []
    for tz in common_timezones:
        if search in tz.lower():
            timezones_list.append(append_offset_to_timezone(tz))
            count += 1
            if count >= search_result_length:
                break

    return jsonify({'status': 'OK', 'data': timezones_list})


@settings.route('/timezone-list', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'timezone')
def get_all_timezones():
    data = ['{0} ({1})'.format(tz, datetime.now(timezone(tz)).strftime('%z'))
            for tz in common_timezones]
    return jsonify({'status': 'OK', 'data': data})


class SystemSettingsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]
    public_settings = ('billing_type', 'billing_url',
                       'persitent_disk_max_size', 'max_kubes_per_container')

    def get(self, sid):
        if sid is None:
            data = enrich_with_plugin_list(SystemSettings.get_all())
        else:
            data = enrich_with_plugin_list(SystemSettings.get(sid))
        if check_permission('read_private', 'system_settings'):
            return data
        if check_permission('read', 'system_settings'):
            if sid is None:
                return [setting for setting in data
                        if setting.get('name') in self.public_settings]
            if data.get('name') in self.public_settings:
                return data
        raise PermissionDenied()

    @check_permission('write', 'system_settings')
    def post(self):
        pass

    @check_permission('write', 'system_settings')
    def put(self, sid):
        params = self._get_params()
        value = params.get('value')
        check_system_settings(params)
        if value is not None:
            SystemSettings.set(sid, value)
    patch = put

    @check_permission('delete', 'system_settings')
    def delete(self, sid):
        pass

register_api(settings, SystemSettingsAPI, 'settings', '/sysapi/', 'sid', 'int',
             strict_slashes=False)
