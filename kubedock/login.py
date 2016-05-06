from flask import (current_app, g, request, abort, has_request_context,
                   _request_ctx_stack, session, Response)
from functools import wraps
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer,
                          BadSignature, SignatureExpired)
from hashlib import md5
import datetime
from werkzeug.local import LocalProxy


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

    def _load_from_token2(self, token='token2'):
        user = None
        token = _token2_loader(token)
        if token and self.user_callback:
            user = self.user_callback(token.get('user_id'))
        if user is not None:
            self.reload_user(user=user)
            #app = current_app._get_current_object()
            #user_loaded_from_header.send(app, user=_get_user())
        else:
            self.reload_user()

    def _load_from_header(self, header='X-Auth-Token'):
        user = None
        token = _header_loader(header)
        if token and self.user_callback:
            user = self.user_callback(token.get('user_id'))
        if user is not None:
            self.reload_user(user=user)
            #app = current_app._get_current_object()
            #user_loaded_from_header.send(app, user=_get_user())
        else:
            self.reload_user()

    def _load_user(self):
        is_missing_user_id = 'user_id' not in session
        if is_missing_user_id:
            header_name = 'X-Auth-Token'
            if header_name in request.headers:
                return self._load_from_header(request.headers[header_name])
            token_name = 'token2'
            if token_name in request.args:
                return self._load_from_token2(request.args[token_name])
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


def _create_identifier():
    user_agent = request.headers.get('User-Agent')
    if user_agent is not None:
        user_agent = user_agent.encode('utf-8')
    base = '{0}|{1}'.format(_get_remote_addr(), user_agent)
    if str is bytes:
        base = unicode(base, 'utf-8', errors='replace')  # pragma: no cover
    h = md5()
    h.update(base.encode('utf8'))
    return h.hexdigest()


def login_user(user):
    user_id = getattr(user, ID_ATTRIBUTE)()
    session['user_id'] = user_id
    session['_fresh'] = True
    session['_id'] = _create_identifier()
    _request_ctx_stack.top.user = user
    return True


def logout_user():
    for key in ('user_id', '_fresh'):
        session.pop(key, None)


def _get_user():
    if has_request_context() and not hasattr(_request_ctx_stack.top, 'user'):
        current_app.login_manager._load_user()
    return getattr(_request_ctx_stack.top, 'user', None)


def process_jwt(token, throw=True):
    s = Serializer(current_app.config.get('SECRET_KEY'))
    try:
        data, header = s.loads(token, return_header=True)
        return data
    except (BadSignature, SignatureExpired):
        if throw:
            abort(401)


def _header_loader(header='X-Auth-Token'):
    auth = request.headers.get(header)
    if auth is None:
        return
    return process_jwt(auth)


def _token2_loader(token='token2'):
    auth = request.args.get(token)
    if auth is None:
        return
    return process_jwt(auth)


#def make_session(user):
#    secret = current_app.config.get('SECRET_KEY')
#    lifetime = current_app.config.get('SESSION_LIFETIME')
#    user_id = getattr(user, ID_ATTRIBUTE)()
#    data = {
#        'id': session.sid,
#        '_id': session.get('_id'),
#        '_fresh': False,
#        'user_id': user_id}
#    if login:
#        session['user_id'] = user_id
#        session['_fresh'] = data['_fresh'] = True
#        session['_id'] = _create_identifier()
#        _request_ctx_stack.top.user = user
#        secret = current_app.config.get('SECRET_KEY')
#        lifetime = current_app.config.get('SESSION_LIFETIME')
#        s = Serializer(secret, lifetime)
#    token = s.dumps(dict(dict(session), sid=session.sid))
#    return token.decode('ascii')


def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kw):
        if not current_user.is_authenticated():
            token = request.args.get('token')
            user = current_app.login_manager.token_callback(token)
            if user is None or user.deleted:
                abort(401)
            if not user.active:
                abort(403)
            g.user = user
        return func(*args, **kw)
    return wrapper
