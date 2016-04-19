from ..core import db


class RoleForNotification(db.Model):
    __tablename__ = 'notification_roles'
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    nid = db.Column(db.Integer, db.ForeignKey('notifications.id'), primary_key=True, nullable=False)
    rid = db.Column(db.Integer, db.ForeignKey('rbac_role.id'), primary_key=True, nullable=False)
    target = db.Column(db.String(255))
    time_stamp = db.Column(db.DateTime)
    role = db.relationship('Role')


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True, nullable=False)
    type = db.Column(db.String(12), nullable=False)
    message = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    roles = db.relationship('RoleForNotification')
