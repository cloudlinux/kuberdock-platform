from flask import (current_app, g, request, has_request_context,
                   _request_ctx_stack, session)
from functools import wraps
from hashlib import md5
from uuid import uuid4
from werkzeug.local import LocalProxy

from .exceptions import PermissionDenied, NotAuthorized

current_user = LocalProxy(lambda: _get_user())
ID_ATTRIBUTE = 'get_id'


class AnonymousUserMixin(object):

    def is_authenticated(self):
        return False

    def is_active(self):
        return False

    def is_anonymous(self):
        return True

    def get_id(self):
        return


class UserMixin(object):

    def is_active(self):
        return True

    def is_authenticated(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.id)
        except AttributeError:
            raise NotImplementedError('No `id` attribute - override `get_id`')

    def __eq__(self, other):
        if isinstance(other, UserMixin):
            return self.get_id() == other.get_id()
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal


class LoginManager(object):

    def __init__(self, app=None):
        self.anonymous_user = AnonymousUserMixin
        self.user_callback = None
        self.token_callback = None
        self.cleaner_callback = None
        self.adder_callback = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.login_manager = self

    def user_loader(self, callback):
        self.user_callback = callback
        return callback

    def token_loader(self, callback):
        self.token_callback = callback
        return callback

    def session_cleaner(self, callback):
        self.cleaner_callback = callback
        return callback

    def session_adder(self, callback):
        self.adder_callback = callback
        return callback

    def _load_user(self):
        # We simply have no additional places to look for users auth data
        return self.reload_user()

    def reload_user(self, user=None):
        ctx = _request_ctx_stack.top
        if user is None:
            user_id = session.get('user_id')
            if user_id is None:
                ctx.user = self.anonymous_user()
            else:
                user = self.user_callback(user_id)
                if user is None:
                    logout_user()
                else:
                    ctx.user = user
        else:
            ctx.user = user


def _get_remote_addr():
    address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if address is not None:
        address = address.encode('utf-8')
    return address


def create_identifier():
    user_agent = request.headers.get('User-Agent')
    if user_agent is not None:
        user_agent = user_agent.encode('utf-8')
    base = '{0}|{1}'.format(_get_remote_addr(), user_agent)
    if str is bytes:
        base = unicode(base, 'utf-8', errors='replace')  # pragma: no cover
    h = md5()
    h.update(base.encode('utf8'))
    return h.hexdigest()


def login_user(user, DB=True):
    user_id = getattr(user, ID_ATTRIBUTE)()
    session['user_id'] = user_id
    session['_fresh'] = True
    session['_id'] = create_identifier()
    _request_ctx_stack.top.user = user
    if session.sid is None:
        session.sid = str(uuid4())
    if DB and current_app.login_manager.adder_callback:
        current_app.login_manager.adder_callback(session.sid, user_id, user.role_id)
    return True


def logout_user(DB=True):
    for key in ('user_id', '_fresh'):
        session.pop(key, None)
    if DB and current_app.login_manager.cleaner_callback:
        current_app.login_manager.cleaner_callback(session.sid)


def _get_user():
    if has_request_context() and not hasattr(_request_ctx_stack.top, 'user'):
        current_app.login_manager.reload_user()
    return getattr(_request_ctx_stack.top, 'user', None)


def get_user_role(user=None):
    rolename = 'AnonymousUser'
    if user is not None:
        rolename = user.role.rolename
    else:
        try:
            rolename = current_user.role.rolename
        except AttributeError:
            try:
                rolename = g.user.role.rolename
            except AttributeError:
                pass
    if rolename == 'AnonymousUser' and user is None:
        logout_user()
    return rolename


def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kw):
        if not current_user.is_authenticated():
            token = request.args.get('token')
            user = current_app.login_manager.token_callback(token)
            if user is None or user.deleted:
                raise NotAuthorized
            if not user.active:
                raise PermissionDenied
            g.user = user
        return func(*args, **kw)
    return wrapper
