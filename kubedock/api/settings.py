import json
from flask import Blueprint, request, jsonify

from ..core import db
from ..rbac import check_permission, init_permissions
from ..rbac.models import Role, Resource, Permission
from ..utils import login_required_or_basic, APIError, get_model
from ..notifications.events import EVENTS, NotificationEvent


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
@login_required_or_basic
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
    init_permissions()
    return jsonify({'status': 'OK'})


#########################
### Notifications API ###
def to_dict(x):
    return dict(id=x.id, subject=x.subject, event=EVENTS[x.event],
                event_id=x.event, text_plain=x.text_plain,
                text_html=x.text_html, as_html=x.as_html)


@check_permission("get_notifications", "settings")
def get_notifications():
    objects_list = db.session.query(get_model('notification_template')).all()
    notifications = [to_dict(obj) for obj in objects_list]
    events_keys = NotificationEvent.get_events_keys()
    templates = db.session.query(get_model('notification_template')).all()
    exist_events = [t.event for t in templates]
    events = NotificationEvent.get_events(exclude=exist_events)
    return events_keys, notifications, events


@settings.route('/notifications/<tid>', methods=['GET'])
@check_permission('get_notifications', 'settings')
def get_template(tid):
    t = db.session.query(get_model('notification_template')).get(id=tid).first()
    if t:
        return jsonify({'status': True, 'data': t.to_dict()})
    raise APIError("Template {0} doesn't exists".format(tid), 404)


@settings.route('/notifications', methods=['POST'])
@check_permission('create_notifications', 'settings')
def create_template():
    data = request.json
    event = data['event']
    model = db.session.query(get_model('notification_template'))
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
@check_permission('edit_notifications', 'settings')
def put_template(tid):
    model = db.session.query(get_model('notification_template'))
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
@check_permission('delete_notifications', 'settings')
def delete_template(tid):
    t = db.session.query(get_model('notification_template')).get(tid)
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