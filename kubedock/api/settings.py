from pytz import common_timezones, timezone
from flask import Blueprint, request, jsonify, current_app
from flask.views import MethodView

from ..exceptions import PermissionDenied
from ..login import auth_required
from ..rbac import check_permission
from ..utils import KubeUtils, register_api
from ..users.utils import append_offset_to_timezone
from ..kapi.notifications import read_role_events
from ..static_pages.models import MenuItem
from ..system_settings.models import SystemSettings
from ..validation import check_system_settings


settings = Blueprint('settings', __name__, url_prefix='/settings')


def enrich_with_plugin_list(data):
    # TODO: move DNS data to database
    plugins = ['No billing'] + \
        current_app.billing_factory.list_billing_plugins()
    dns_backends = [
        'No provider',
        'cpanel_dnsonly',
        'aws_route53',
        'cloudflare',
    ]
    if isinstance(data, list):
        btype = [i for i in data if i.get('name') == 'billing_type']
        if btype:
            btype[0]['options'] = plugins
        dns = [i for i in data if i.get('name') == 'dns_management_system']
        if dns:
            dns[0]['options'] = dns_backends
    elif isinstance(data, dict):
        if data.get('name') == 'billing_type':
            data['options'] = plugins
        if data.get('name') == 'dns_management_system':
            data['options'] = dns_backends
    return data


@settings.route('/notifications', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_notifications():
    return read_role_events(KubeUtils.get_current_user().role)


@settings.route('/menu', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_menu():
    return MenuItem.get_menu()


@settings.route('/timezone', methods=['GET'])
@auth_required
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
@auth_required
@check_permission('get', 'timezone')
def get_all_timezones():
    data = [append_offset_to_timezone(tz) for tz in common_timezones]
    return jsonify({'status': 'OK', 'data': data})


class SystemSettingsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, auth_required]
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
        return self.get(sid)

    patch = put

    @check_permission('delete', 'system_settings')
    def delete(self, sid):
        pass

register_api(settings, SystemSettingsAPI, 'settings', '/sysapi/', 'sid', 'int',
             strict_slashes=False)
