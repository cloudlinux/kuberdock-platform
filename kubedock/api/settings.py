import json
from pytz import common_timezones, timezone
from datetime import datetime
from flask import Blueprint, request, jsonify
#from flask.ext.login import current_user
from flask.views import MethodView

from ..core import db
from ..rbac import check_permission, acl
from ..rbac.models import Role, Resource, Permission
from ..decorators import login_required_or_basic_or_token
from ..utils import APIError, KubeUtils, register_api
from ..users.utils import append_offset_to_timezone
from ..notifications.events import EVENTS, NotificationEvent
from ..notifications.models import NotificationTemplate
from ..system_settings.models import SystemSettings
from ..validation import check_system_settings

settings = Blueprint('settings', __name__, url_prefix='/settings')


@check_permission("get_permissions", "settings")
def get_permissions():
    data = []
    roles = {r.id: r.to_dict() for r in Role.all()}
    for res in Resource.all():
        perms = set()
        _roles = {}
        for p in res.permissions:
            perms.add(p.name)
            role = roles[p.role_id]
            rolename = role['rolename']
            if rolename in _roles:
                _roles[rolename].append(p.to_dict())
            else:
                _roles[rolename] = [p.to_dict()]
        data.append({'id': res.id, 'name': res.name, 'permissions': list(perms),
                     'roles': _roles, 'all_roles': roles})
    return roles, data


@settings.route('/permissions/<pid>', methods=['PUT'])
@login_required_or_basic_or_token
@check_permission("set_permissions", "settings")
def permissions(pid):
    data = request.json or request.form.to_dict()
    allow = data.get('allow')
    if allow not in ('true', 'false', True, False):
        raise APIError("Value error: {0}".format(allow))
    perm = Permission.query.get(int(pid))
    if allow in ('true', True):
        perm.set_allow()
    else:
        perm.set_deny()
    acl.init_permissions()
    return jsonify({'status': 'OK'})


#########################
### Notifications API ###
def to_dict(x):
    return dict(id=x.id, subject=x.subject, event=EVENTS[x.event],
                event_id=x.event, text_plain=x.text_plain,
                text_html=x.text_html, as_html=x.as_html)


@check_permission("get_notifications", "settings")
def get_notifications():
    objects_list = db.session.query(NotificationTemplate).all()
    notifications = [to_dict(obj) for obj in objects_list]
    events_keys = NotificationEvent.get_events_keys()
    templates = db.session.query(NotificationTemplate).all()
    exist_events = [t.event for t in templates]
    events = NotificationEvent.get_events(exclude=exist_events)
    return events_keys, notifications, events


@settings.route('/notifications/<tid>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get_notifications', 'settings')
def get_template(tid):
    t = db.session.query(NotificationTemplate).get(id=tid).first()
    if t:
        return jsonify({'status': True, 'data': t.to_dict()})
    raise APIError("Template {0} doesn't exists".format(tid), 404)


@settings.route('/notifications', methods=['POST'])
@login_required_or_basic_or_token
@check_permission('create_notifications', 'settings')
def create_template():
    data = request.json
    event = data['event']
    model = db.session.query(NotificationTemplate)
    t = model.filter_by(event=data['event']).first()
    if t:
        raise APIError('Conflict: Template with event "{0}" already '
                       'exists'.format(NotificationEvent.get_event_name(event)))
    try:
        t = model(**data)
        db.session.add(t)
        db.session.commit()
    except Exception, e:
        db.session.rollback()
        return jsonify({'status': 'Operation failed with ex({0})'.format(e)})
    return jsonify({'status': 'OK', 'data': t.to_dict()})


@settings.route('/notifications/<tid>', methods=['PUT'])
@login_required_or_basic_or_token
@check_permission('edit_notifications', 'settings')
def put_template(tid):
    model = db.session.query(NotificationTemplate)
    t = model.filter_by(id=tid).first()
    if t:
        try:
            data = request.json
            t.subject = data['subject']
            t.text_plain = data['text_plain']
            t.text_html = data['text_html']
            t.as_html = data['as_html']
            db.session.add(t)
            db.session.commit()
            return jsonify({'status': 'OK', 'data': to_dict(t.__dict__)})
        except KeyError, e:
            raise APIError("Template '{0}' update failed: {1} ({2})".format(
                tid, e.message, json.dumps(data)))
        except Exception, e:
            db.session.rollback()
            raise APIError("Template '{0}' update failed: {1}".format(
                tid, e.message))
    raise APIError("Template {0} doesn't exists".format(tid), 404)


@settings.route('/<tid>', methods=['DELETE'])
@login_required_or_basic_or_token
@check_permission('delete_notifications', 'settings')
def delete_template(tid):
    t = db.session.query(NotificationTemplate).get(tid)
    if t:
        try:
            db.session.delete(t)
            db.session.commit()
            return jsonify({'status': 'OK'})
        except Exception, e:
            db.session.rollback()
            raise APIError("Template '{0}' delete failed: {1}".format(
                tid, e.message))
    raise APIError("Template {0} doesn't exists".format(tid), 404)


@settings.route('/timezone', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get_timezone', 'settings')
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
@check_permission('get_timezone', 'settings')
def get_all_timezones():
    data = ['{0} ({1})'.format(tz, datetime.now(timezone(tz)).strftime('%z'))
                for tz in common_timezones]
    return jsonify({'status': 'OK', 'data': data})


class SystemSettingsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]

    def get(self, sid):
        if sid is None:
            return SystemSettings.get_all()
        return SystemSettings.get(sid)

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

    @check_permission('delete', 'system_settings')
    def delete(self, sid):
        pass

register_api(settings, SystemSettingsAPI, 'settings', '/sysapi/', 'sid', 'int', strict_slashes=False)