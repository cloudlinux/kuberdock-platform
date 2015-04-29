import json
import datetime
from sqlalchemy.dialects import postgresql
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from flask.ext.login import UserMixin

from ..core import db, login_manager
from ..models_mixin import BaseModelMixin
from .signals import (
    user_logged_in, user_logged_out, user_logged_in_by_another,
    user_logged_out_by_another)
from .utils import get_user_last_activity, get_online_users


@login_manager.user_loader
def load_users(user_id):
    return User.query.get(int(user_id))


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
    role_id = db.Column(db.Integer, db.ForeignKey('rbac_role.id'))
    permission_id = db.Column(db.Integer, db.ForeignKey('rbac_permission.id'))
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'))
    join_date = db.Column(db.DateTime, default=datetime.datetime.now)
    pods = db.relationship('Pod', backref='owner', lazy='dynamic')
    activities = db.relationship('UserActivity', back_populates="user")
    settings = db.Column(db.Text)

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
        if self.role.rolename == 'Admin':
            return True
        else:
            return False

    @property
    def last_activity(self):
        return get_user_last_activity(self.id)

    def pods_to_dict(self, exclude=None):
        states = lambda x: dict(
            pod_id=x.pod_id,
            container_name=x.container_name,
            kubes=x.kubes,
            start_time=x.start_time.isoformat(sep=' ')[:19]
                if x.start_time else None,
            end_time=x.end_time.isoformat(sep=' ')[:19]
                if x.end_time else None
        )
        return [
            dict(
                id=p.id,
                name=p.name,
                owner_id=p.owner_id,
                kube_id=p.kube_id,
                config=p.config,
                status=p.status,
                kubes=p.kubes,
                containers_count=p.containers_count,
                states=[states(state) for state in p.states]
            ) for p in self.pods if not p.is_deleted
        ]

    def get_settings(self):
        return json.loads(self.settings) if self.settings else {}

    def set_settings(self, k, v):
        data = self.get_settings()
        data[k] = v
        self.settings = json.dumps(data)
        self.save()

    def to_dict(self):
        valid = ['id', 'username', 'email', 'first_name', 'last_name',
                 'middle_initials', 'active', 'suspended']
        data = dict([(k, v) for k, v in vars(self).items() if k in valid])
        data['rolename'] = self.role.rolename
        data['package'] = self.package.name
        return data

    def to_full_dict(self, include=None, exclude=None):
        last_activity = self.last_activity
        package = self.package.name if self.package else None
        last_login = self.last_login
        pods = self.pods_to_dict()
        containers_count = sum([p['containers_count'] for p in pods])
        data = dict(
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
            pods=pods,
            containers_count=containers_count,
            pods_count=len(pods),
            package_info=self.package_info(),
            last_activity=last_activity.isoformat(sep=' ')[:19] \
                if last_activity else '',
            last_login=last_login.isoformat(sep=' ')[:19] \
                if last_login else None
        )

        return data

    def history_logged_in(self):
        ua = UserActivity.create(action=UserActivity.LOGIN, user_id=self.id)
        ua.save()

    def history_logged_out(self):
        ua = UserActivity.create(action=UserActivity.LOGOUT, user_id=self.id)
        ua.save()

    def user_activity(self):
        data = [ua.to_dict() for ua in self.activities]
        return data

    @property
    def last_login(self):
        last_login = UserActivity.filter_by(
            action=UserActivity.LOGIN,
            user_id=self.id).order_by(UserActivity.ts.desc()).first()
        if last_login:
            return last_login.ts
        return None

    def package_info(self):
        pkg = self.package
        if pkg is None:
            return {}
        return dict(
            id=pkg.id,
            name=pkg.name,
            kube_id=pkg.kube_id,
            kube_info=pkg.kube.to_dict() if pkg.kube_id else {},
            amount=pkg.amount,
            currency=pkg.currency,
            period=pkg.period
        )

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
    remote_ip = db.Column(db.String)

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
        data = [a.to_dict(include={'user': users.get(a.user_id)})
                for a in activities]
        if to_json:
            return json.dumps(data)
        return activities

    @classmethod
    def get_sessions(cls, user_id, date_from=None, date_to=None):
        activities = cls.query.filter_by(user_id=user_id)
        if date_from:
            activities = activities.filter(
                cls.ts >= '{0} 00:00:00'.format(date_from))
        if date_to:
            activities = activities.filter(
                cls.ts <= '{0} 23:59:59'.format(date_to))
        a = None
        b = None
        history = []
        for act in activities:
            action = act.action
            if action == cls.LOGIN:
                if a is None:
                    a = act
            elif action == cls.LOGIN_A:
                if b is None:
                    b = act
            elif action == cls.LOGOUT:
                if a:
                    history.append((a.ts, (act.ts - a.ts).seconds, act.ts,
                                    a.remote_ip, action))
                    a = None
            elif action == cls.LOGOUT_A:
                if b:
                    history.append((b.ts, (act.ts - b.ts).seconds, act.ts,
                                    b.remote_ip, action))
                    b = None
        return history

    def to_dict(self, include=None, exclude=None):
        data = dict(
            id=self.id,
            ts=self.ts.isoformat(sep=' ')[:19],
            action=UserActivity.ACTIONS.get(self.action),
            user_id=self.user_id,
            remote_ip=self.remote_ip or ''
        )
        if isinstance(include, dict):
            data.update(include)
        return data


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
def user_logged_in_signal(args):
    user_id, remote_ip = args
    current_app.logger.debug('user_logged_in_signal {0}'.format(user_id))
    ua = UserActivity.create(
        action=UserActivity.LOGIN, user_id=user_id, remote_ip=remote_ip)
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
