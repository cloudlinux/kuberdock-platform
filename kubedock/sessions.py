import base64
import hmac
import hashlib
import random
import string
import datetime
from uuid import uuid4

from itsdangerous import (JSONWebSignatureSerializer as FallbackSerializer,
                          TimedJSONWebSignatureSerializer as Serializer,
                          BadSignature, SignatureExpired)

from sqlalchemy.exc import ResourceClosedError, IntegrityError
from werkzeug.datastructures import CallbackDict
from flask.sessions import SessionInterface, SessionMixin

from flask import current_app
from .users.models import SessionData, User
from .core import db
#from .login import process_jwt, make_session,


def _generate_sid():
    return str(uuid4())


#def _calc_hmac(body, secret):
#    return base64.b64encode(hmac.new(secret, body, hashlib.sha1).digest())


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
        if not token:   # new unauthirized request
            return self.manager.new_session()
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
            print 'save_session is empty for sid:{0}'.format(session.sid)
            return
        user_id = session.get('user_id')
        if user_id is None:
            return
        secret = current_app.config.get('SECRET_KEY')
        lifetime = current_app.config.get('SESSION_LIFETIME')
        s = Serializer(secret, lifetime)
        token = s.dumps(dict(dict(session), sid=session.sid))
        response.headers['X-Auth-Token'] = token.decode('ascii')

class DataBaseSessionManager(SessionManager):

    def remove(self, sid=None):
        if not sid:
            return
        saved = db.session.query(SessionData).get(sid)
        if saved is not None:
            db.session.delete(saved)
            db.session.commit()

    def new_session(self):
        return ManagedSession()

    def get(self, data):
        sid = data.pop('sid', None)
        if sid is None:
            sid = _generate_sid()
            try:
                db.session.add(SessionData(id=sid))
                db.session.commit()
            except (ResourceClosedError, IntegrityError):
                db.session.rollback()
            return ManagedSession(sid=sid, initial=data)
        saved = SessionData.query.get(sid)
        if saved is None:
            try:
                db.session.add(SessionData(id=sid))
                db.session.commit()
            except (ResourceClosedError, IntegrityError):
                db.session.rollback()
            return ManagedSession(sid=sid, initial=data)
        current_app.logger.debug([data, sid])
        return ManagedSession(sid=sid, initial=data)
