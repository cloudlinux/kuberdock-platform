import json
import datetime
from sqlalchemy.dialects import postgresql
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from flask.ext.login import UserMixin

from ..core import db, login_manager
from .utils import get_user_last_activity, get_online_users
from ..models_mixin import BaseModelMixin
from .signals import (
    user_logged_in, user_logged_out, user_logged_in_by_another,
    user_logged_out_by_another)


@login_manager.user_loader
def load_users(user_id):
    return db.session.query(User).get(int(user_id))


class User(BaseModelMixin, UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    middle_initials = db.Column(db.String(128), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=False)
    suspended = db.Column(db.Boolean, nullable=False, default=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'))
    join_date = db.Column(db.DateTime, default=datetime.datetime.now)
    pods = db.relationship('Pod', backref='owner', lazy='dynamic')
    activities = db.relationship('UserActivity', back_populates="user")

    @classmethod
    def get_online_collection(cls, to_json=None):
        user_ids = get_online_users()
        users = [u.to_dict() for u in cls.query.filter(cls.id.in_(user_ids))]
        if to_json:
            return json.dumps(users)
        return users

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_administrator(self):     # TODO remove this, prefer normal permission check
        if self.role.rolename == 'SuperAdmin':
            return True
        else:
            return False

    @property
    def last_activity(self):
        return get_user_last_activity(self.id)

    def to_dict(self, include=None, exclude=None):
        last_activity = self.last_activity
        package = self.package.name if self.package else None
        return dict(
            id=self.id,
            username=self.username,
            email=self.email,
            active=self.active,
            first_name=self.first_name,
            last_name=self.last_name,
            middle_initials=self.middle_initials,
            suspended=self.suspended,
            rolename=self.role.rolename,
            join_date=self.join_date.isoformat(sep=' ')[:19],
            package=package,
            last_activity=last_activity.isoformat(sep=' ')[:19] \
                if last_activity else '', )

    def history_logged_in(self):
        ua = UserActivity.create(action=UserActivity.LOGIN, user_id=self.id)
        ua.save()

    def history_logged_out(self):
        ua = UserActivity.create(action=UserActivity.LOGOUT, user_id=self.id)
        ua.save()

    def user_activity(self):
        data = [ua.to_dict() for ua in self.activities]
        return data

    def __repr__(self):
        return "<User(username='{0}', email='{1}')>".format(self.username, self.email)
    

class UserActivity(BaseModelMixin, db.Model):
    __tablename__ = 'users_activity'

    LOGIN, LOGOUT, LOGIN_A, LOGOUT_A = 0, 1, 2, 3
    ACTIONS = {
        LOGIN: 'login',
        LOGOUT: 'logout',
        LOGIN_A: 'login_by_another',
        LOGOUT_A: 'logout_by_another',
    }

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ts = db.Column(db.DateTime, default=datetime.datetime.now)
    action = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User')

    @classmethod
    def get_users_activities(cls, user_ids, date_from=None, date_to=None,
                             to_dict=None, to_json=None):
        activities = cls.query.filter(cls.user_id.in_(user_ids))
        if date_from:
            activities = activities.filter(
                cls.ts >= '{0} 00:00:00'.format(date_from))
        if date_to:
            activities = activities.filter(
                cls.ts <= '{0} 23:59:59'.format(date_to))
        users = User.filter(User.id.in_([a.user_id for a in activities]))
        users = {u.id: u.to_dict() for u in users}
        if to_dict:
            data = [a.to_dict(include={'user': users.get(a.user_id)})
                    for a in activities]
            return data
        if to_json:
            return json.dumps([a.to_dict(include={'user': users.get(a.user_id)})
                               for a in activities])
        return activities

    def to_dict(self, include=None, exclude=None):
        data = dict(
            id=self.id,
            ts=self.ts.isoformat(sep=' ')[:19],
            action=UserActivity.ACTIONS.get(self.action),
            user_id=self.user_id
        )
        if isinstance(include, dict):
            data.update(include)
        return data


class Role(BaseModelMixin, db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    rolename = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')
    
    def __repr__(self):
        return "<Role(rolename='{0}')>".format(self.rolename)


class SessionData(db.Model):
    __tablename__ = 'session_data'
    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    data = db.Column(db.PickleType, nullable=True)
    time_stamp = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, id, data=None):
        self.id = id
        self.data = data
        self.time_stamp = datetime.datetime.now()

    def __repr__(self):
        return "<SessionData(session_id='%s', data='%s', time_stamp='%s')>" % (
            self.session_id, self.data, self.time_stamp)


#####################
### Users signals ###
@user_logged_in.connect
def user_logged_in_signal(user_id):
    current_app.logger.debug('user_logged_in_signal {0}'.format(user_id))
    ua = UserActivity.create(action=UserActivity.LOGIN, user_id=user_id)
    ua.save()


@user_logged_out.connect
def user_logged_out_signal(user_id):
    current_app.logger.debug('user_logged_out_signal {0}'.format(user_id))
    ua = UserActivity.create(action=UserActivity.LOGOUT, user_id=user_id)
    ua.save()


@user_logged_in_by_another.connect
def user_logged_in_by_another_signal(args):
    user_id, target_user_id = args
    current_app.logger.debug('user_logged_in_by_another {0} -> {1}'.format(
        user_id, target_user_id))
    ua = UserActivity.create(action=UserActivity.LOGIN_A, user_id=user_id)
    ua.save()


@user_logged_out_by_another.connect
def user_logged_out_by_another_signal(args):
    user_id, target_user_id = args
    current_app.logger.debug('user_logged_out_by_another {0} -> {1}'.format(
        user_id, target_user_id))
    ua = UserActivity.create(action=UserActivity.LOGOUT_A,
                             user_id=target_user_id)
    ua.save()
