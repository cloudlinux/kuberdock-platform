import datetime
import hashlib
import json

from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ResourceClosedError, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

# from flask import current_app
#from flask.ext.login import UserMixin
from ..login import UserMixin
from ..core import db, login_manager
from ..models_mixin import BaseModelMixin
from .signals import (
    user_logged_in, user_logged_out, user_logged_in_by_another,
    user_logged_out_by_another, user_get_all_settings, user_get_setting,
    user_set_setting)
from .utils import (
    get_user_last_activity, get_online_users, enrich_tz_with_offset)
from ..settings import DEFAULT_TIMEZONE


@login_manager.user_loader
def load_user_by_id(user_id):
    return User.query.get(int(user_id))


@login_manager.token_loader
def load_user_by_token(token):
    if token is None:
        return
    return User.query.filter_by(token=token).first()


@login_manager.session_cleaner
def clean_session(sid):
    if sid is None:
        return
    session = SessionData.query.get(sid)
    if session is None:
        return
    db.session.delete(session)
    db.session.commit()

@login_manager.session_adder
def add_session(sid, uid, rid):
    if sid is None:
        return
    try:
        db.session.add(SessionData(id=sid, user_id=uid, role_id=rid))
        db.session.commit()
    except (ResourceClosedError, IntegrityError):
        db.session.rollback()


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
    deleted = db.Column(db.Boolean, nullable=False, default=False)
    role_id = db.Column(db.Integer, db.ForeignKey('rbac_role.id'))
    permission_id = db.Column(db.Integer, db.ForeignKey('rbac_permission.id'))
    package_id = db.Column(
        db.Integer, db.ForeignKey('packages.id'), nullable=False,
        # Used raw query 'cause cannot import Package model (unresolvable
        # circular dependency).
        default=db.text('(select id from packages where is_default)'))
    join_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    pods = db.relationship('Pod', backref='owner', lazy='dynamic')
    activities = db.relationship('UserActivity', back_populates="user")
    settings = db.Column(db.Text)
    token = db.Column(db.String(96), nullable=True)
    timezone = db.Column(db.String(64), nullable=False,
                         default=DEFAULT_TIMEZONE,
                         server_default=DEFAULT_TIMEZONE)
    clientid = db.Column(db.Integer, nullable=True, unique=True)

    # This fields(+password) can be seen and edited by user himself
    # Admins can edit them too
    profile_fields = ['email', 'first_name', 'last_name', 'middle_initials',
                      'timezone']

    class __metaclass__(db.Model.__class__):
        @property
        def not_deleted(cls):
            return cls.query.filter_by(deleted=False)

    @property
    def fix_price(self):
        return self.package.count_type == 'fixed'

    @classmethod
    def get_internal(cls):
        return cls.get(0)

    @classmethod
    def username_iequal(cls, username):
        """Get case-insensitive comparison condition for query.filter"""
        return db.func.lower(cls.username) == username.lower()

    @classmethod
    def get(cls, uid):
        """Get User by id, case-insensitive username or User object."""
        if uid is None:
            return
        if isinstance(uid, cls):
            return cls.query.get(uid.id)
        uid = str(uid)
        if uid.isdigit():
            return cls.query.get(uid)
        return cls.query.filter(cls.username_iequal(uid)).first()

    @classmethod
    def get_online_collection(cls, to_json=None):
        user_ids = get_online_users()
        users = [u.to_dict() for u in cls.not_deleted.filter(cls.id.in_(user_ids))]
        if to_json:
            return json.dumps(users)
        return users

    @classmethod
    def search_usernames(cls, s, with_deleted=False):
        users = cls.query if with_deleted else cls.not_deleted
        condition = db.func.lower(cls.username).contains(s.lower())
        usernames = list(users.filter(condition).values(cls.username))
        return zip(*usernames)[0] if usernames else []

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def verify_token(self, token):
        return self.token is not None and self.token == token

    def is_administrator(self):
        if self.role.rolename == 'Admin':
            return True
        else:
            return False

    def is_trial(self):
        return self.role.rolename == 'TrialUser'

    @property
    def last_activity(self):
        return get_user_last_activity(self.id)

    def pods_to_dict(self, exclude=None):
        if exclude is None:
            exclude = []
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
            ) for p in self.pods if not p.is_deleted
        ]

    def get_settings(self, key=None):
        user_settings = json.loads(self.settings) if self.settings else {}
        if key is not None:
            return user_settings.get(key)
        return user_settings

    def set_settings(self, k, v):
        data = self.get_settings()
        data[k] = v
        self.settings = json.dumps(data)
        self.save()

    @enrich_tz_with_offset(['timezone'])
    def to_dict(self, for_profile=False, full=False, exclude=None):

        if for_profile and full:
            raise RuntimeWarning('Serialize user for profile or full, not both')

        if for_profile:
            valid = self.profile_fields + ['id', 'username', 'package_id', 'clientid']
            data = {k: v for k, v in super(User, self).to_dict().items() if k in valid}
            data['rolename'] = self.role.rolename if self.role else None
            return data

        valid = self.profile_fields + ['id', 'username', 'active', 'suspended']
        data = {k: v for k, v in super(User, self).to_dict().items() if k in valid}
        data['rolename'] = self.role.rolename if self.role else None
        data['package'] = self.package.name if self.package else None

        if full:
            # add all extra fields
            last_activity = self.last_activity
            last_login = self.last_login
            pods = self.pods_to_dict(exclude)
            containers_count = sum([p['containers_count'] for p in pods])
            data['pods'] = pods
            data['pods_count'] = len(pods)
            data['containers_count'] = containers_count
            data['package_info'] = self.package_info()
            data['join_date'] = self.join_date
            data['last_activity'] = last_activity if last_activity else ''
            data['last_login'] = last_login if last_login else None
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
            kube_id=[package_kube.kube_id for package_kube in pkg.kubes],
            kube_info=[package_kube.kube.to_dict() for package_kube in pkg.kubes],
            first_deposit=pkg.first_deposit,
            currency=pkg.currency,
            period=pkg.period
        )

    def update(self, data, for_profile=False):
        valid = self.profile_fields + ['password']
        if not for_profile:
            valid = valid + ['active', 'suspended', 'role', 'permission',
                             'package', 'join_date', 'settings']
        for key, value in data.items():
            if key in valid:
                setattr(self, key, value)

    def get_token(self, regen=False):
        if not self.token or regen:
            now = datetime.datetime.utcnow()
            epoch = datetime.datetime(1970, 1, 1)
            delta = now - epoch
            seconds = int(delta.total_seconds())
            sha1 = hashlib.sha1()
            sha1.update(self.password_hash)
            sha1.update(str(seconds))
            sha1_hex = sha1.hexdigest()
            self.token = '{0}|{1}|{2}'.format(self.username, seconds, sha1_hex)
        return self.token

    @property
    def kubes(self):
        return sum([pod.kubes for pod in self.pods if not pod.is_deleted])

    def logout(self, commit=True):
        for session in SessionData.query.filter_by(user_id=self.id):
            db.session.delete(session)

        user_logged_out.send(self.id, commit=False)
        if commit:
            db.session.commit()

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
    ts = db.Column(db.DateTime, default=datetime.datetime.utcnow)
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
            ts=self.ts,
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
    time_stamp = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    role_id = db.Column(db.Integer, nullable=False)

    def __init__(self, id, user_id, role_id):
        self.id = id
        self.user_id = user_id
        self.role_id = role_id
        self.time_stamp = datetime.datetime.utcnow()

    def __repr__(self):
        return "<SessionData(id='%s', role_id='%s', time_stamp='%s')>" % (
            self.id, self.role_id, self.time_stamp)


#####################
### Users signals ###
# TODO: by default signals shouldn't commit. It will break transaction in
# the place where signal was sent.

@user_logged_in.connect
def user_logged_in_signal(args):
    user_id, remote_ip = args
    # current_app.logger.debug('user_logged_in_signal {0}'.format(user_id))
    ua = UserActivity.create(
        action=UserActivity.LOGIN, user_id=user_id, remote_ip=remote_ip)
    ua.save()


@user_logged_out.connect
def user_logged_out_signal(user_id, commit=True):
    # current_app.logger.debug('user_logged_out_signal {0}'.format(user_id))
    ua = UserActivity.create(action=UserActivity.LOGOUT, user_id=user_id)
    ua.save(deferred_commit=not commit)


@user_logged_in_by_another.connect
def user_logged_in_by_another_signal(args):
    user_id, target_user_id = args
    # current_app.logger.debug('user_logged_in_by_another {0} -> {1}'.format(
    #     user_id, target_user_id))
    ua = UserActivity.create(action=UserActivity.LOGIN_A, user_id=user_id)
    ua.save()


@user_logged_out_by_another.connect
def user_logged_out_by_another_signal(args):
    user_id, target_user_id = args
    # current_app.logger.debug('user_logged_out_by_another {0} -> {1}'.format(
    #     user_id, target_user_id))
    ua = UserActivity.create(action=UserActivity.LOGOUT_A,
                             user_id=target_user_id)
    ua.save()


@user_get_all_settings.connect
def user_get_all_settings_signal(user_id):
    user = User.query.get(user_id)
    return user.get_settings()


@user_get_setting.connect
def user_get_setting_signal(args):
    user_id, key = args
    user = User.query.get(user_id)
    return user.get_settings(key=key)


@user_set_setting.connect
def user_set_setting_signal(args):
    user_id, key, value = args
    user = User.query.get(user_id)
    user.set_settings(key, value)
