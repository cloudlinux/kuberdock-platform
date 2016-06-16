from datetime import datetime

from kubedock.core import db
from kubedock.notifications.models import Notification, RoleForNotification
from kubedock.rbac.models import Role
from kubedock.utils import send_event_to_role


def attach_admin(message, target=None):
    """
    Save notifications for admin in database and send SSE event to
    web-interface
    """
    message_entry = Notification.query.filter_by(message=message).first()
    if message_entry is None:
        return
    admin_role = Role.query.filter(Role.rolename == 'Admin').one()
    if [r for r in message_entry.roles if r.role == admin_role]:
        return
    evt_entry = RoleForNotification(time_stamp=datetime.now(), target=target)
    evt_entry.role = admin_role
    message_entry.roles.append(evt_entry)
    db.session.commit()
    send_event_to_role('advise:show', {
        'id': evt_entry.id,
        'description': message_entry.description,
        'target': target,
        'type': message_entry.type}, admin_role.id)


def detach_admin(message):
    """
    Delete notifications for admin from database and send SSE event to
    web-interface
    """
    message_entry = Notification.query.filter_by(message=message).first()
    if message_entry is None:
        return
    admin_role = Role.query.filter(Role.rolename == 'Admin').one()
    messages = [r for r in message_entry.roles if r.role == admin_role]
    targets = [{'id': msg.id, 'target': msg.target} for msg in messages]
    try:
        send_event_to_role('advise:hide', targets[0], admin_role.id)
    except IndexError:
        pass
    for message in messages:
        db.session.delete(message)
    db.session.commit()


def read_role_events(role=None):
    """
    Read events from database for a role
    """
    events = []
    if role is None:
        return
    for n in Notification.query.all():
        for r in n.roles:
            if r.role == role:
                events.append({
                    'id': n.id,
                    'type': n.type,
                    'target': r.target,
                    'description': n.description})
    return events
