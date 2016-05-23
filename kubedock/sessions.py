from itsdangerous import (JSONWebSignatureSerializer as FallbackSerializer,
                          TimedJSONWebSignatureSerializer as Serializer,
                          SignatureExpired)

from functools import wraps
from werkzeug.datastructures import CallbackDict
from flask.sessions import SessionInterface, SessionMixin

from flask import current_app, abort, request
from .users.models import SessionData
from .system_settings.models import SystemSettings
from .core import db


def session_required(func):
    @wraps(func)
    def wrapper(*args, **kw):
        sessid = request.args.get('id')
        if sessid is None:
            abort(500)
        sess = SessionData.query.get(sessid)
        if sess is None:
            abort(500)
        return func(*args, **kw)
    return wrapper


def create_token(session):
    secret = SystemSettings.get_by_name('sso_secret_key')
    if not secret:
        secret = current_app.config.get('SECRET_KEY')
    lifetime = current_app.config.get('SESSION_LIFETIME')
    s = Serializer(secret, lifetime)
    token = s.dumps(dict(dict(session), sid=session.sid))
    return token.decode('ascii')


class FakeSessionInterface(SessionInterface):
    def open_session(self, app, req):
        pass

    def save_session(self, app, sess, res):
        pass


class ManagedSession(CallbackDict, SessionMixin):
    def __init__(self, initial=None, sid=None, new=True):
        def on_update(self):
            self.modified = True

        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.new = new
        self.modified = False


class SessionManager(object):
    def new_session(self):
        """Creates a new session"""
        raise NotImplemented

    def exists(self, sid):
        """Does the given session exists"""
        raise NotImplemented

    def remove(self, sid):
        """Remove the session"""
        raise NotImplemented

    def get(self, sid, digest):
        """Retrieve a managed session by session-id,
        checking the HMAC digest"""
        raise NotImplemented

    def put(self, session):
        """Store a managed session"""
        raise NotImplemented


class ManagedSessionInterface(SessionInterface):
    def __init__(self, manager, time_delta):
        self.manager = manager
        self.time_delta = time_delta

    def open_session(self, app, request):
        token = request.headers.get('X-Auth-Token', request.args.get('token2'))
        if not token:   # new unauthorized request
            return self.manager.new_session()
        secret = SystemSettings.get_by_name('sso_secret_key')
        if not secret:
            secret = current_app.config.get('SECRET_KEY')
        lifetime = current_app.config.get('SESSION_LIFETIME')
        try:
            s = Serializer(secret, lifetime)
            data = s.loads(token)
            return self.manager.get(data)
        except SignatureExpired:
            try:
                s = FallbackSerializer(secret)
                data = s.loads(token)
                self.manager.remove(data.get('sid'))
            except Exception:
                return self.manager.new_session()
        except Exception:
            return self.manager.new_session()

    def save_session(self, app, session, response):
        if session.sid is None:
            return
        if not session:
            self.manager.remove(sid=session.sid)
            return
        user_id = session.get('user_id')
        if user_id is None:
            return
        response.headers['X-Auth-Token'] = create_token(session)


class DataBaseSessionManager(SessionManager):

    def remove(self, sid=None):
        if not sid:
            return
        saved = db.session.query(SessionData).get(sid)
        print 'Removing sid:{0}'.format(sid)
        if saved is not None:
            db.session.delete(saved)
            db.session.commit()

    def new_session(self):
        return ManagedSession()

    def get(self, data):
        sid = data.pop('sid', None)
        if sid is None:
            return self.new_session()
        saved = SessionData.query.get(sid)
        if saved is None:
            return self.new_session()
        return ManagedSession(sid=sid, initial=data)

