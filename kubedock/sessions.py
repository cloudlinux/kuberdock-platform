import base64
import hmac
import hashlib
import random
import string
import datetime
from uuid import uuid4

from sqlalchemy.exc import ResourceClosedError
from werkzeug.datastructures import CallbackDict
from flask.sessions import SessionInterface, SessionMixin

from flask import current_app
from .users.models import SessionData
from .core import db

def _generate_sid():
    return str(uuid4())

def _calc_hmac(body, secret):
    return base64.b64encode(hmac.new(secret, body, hashlib.sha1).digest())

class FakeSessionInterface(SessionInterface):
    def open_session(self, app, req):
        pass
    def save_session(self, app, sess, res):
        pass

class ManagedSession(CallbackDict, SessionMixin):
    def __init__(self, initial=None, sid=None, new=False, randval=None, hmac_digest=None):
        def on_update(self):
            self.modified = True

        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.new = new
        self.modified = False
        self.randval = randval
        self.hmac_digest = hmac_digest

    def sign(self, secret):
        if not self.hmac_digest:
            self.randval = ''.join(random.sample(string.lowercase+string.digits, 20))
            self.hmac_digest = _calc_hmac('%s:%s' % (self.sid, self.randval), secret)

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
        """Retrieve a managed session by session-id, checking the HMAC digest"""
        raise NotImplemented
    def put(self, session):
        """Store a managed session"""
        raise NotImplemented

class ManagedSessionInterface(SessionInterface):
    def __init__(self, manager, skip_paths, cookie_timedelta):
        self.manager = manager
        self.skip_paths = skip_paths
        self.cookie_timedelta = cookie_timedelta

    def get_expiration_time(self, app, session):
        if session.permanent:
            return app.permament_session_lifetime
        return datetime.datetime.now() + self.cookie_timedelta

    def open_session(self, app, request):
        cookie_val = request.cookies.get(app.session_cookie_name)

        if not cookie_val or '!' not in cookie_val:
            # Don't bother creating a cookie for static resources
            for sp in self.skip_paths:
                if request.path.startswith(sp):
                    return None
            # cookie missing
            # current_app.logger.debug('missing cookie')
            return self.manager.new_session()
        sid, digest = cookie_val.split('!', 1)
        if self.manager.exists(sid):
            return self.manager.get(sid, digest)
        return self.manager.new_session()

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app);
        if not session:
            self.manager.remove(session.sid)
            if session.modified:
                response.delete_cookie(app.session_cookie_name, domain=domain)
            return
        if not session.modified:
            # no need to save an unaltered session
            # TODO: put logic here to test if the cookie is older than N days, if so, update expiration date
            return
        self.manager.put(session)
        session.modified = False

        cookie_exp = self.get_expiration_time(app, session)
        response.set_cookie(app.session_cookie_name,
                            '%s!%s' % (session.sid, session.hmac_digest),
                            expires=cookie_exp, httponly=True, domain=domain)

class DataBaseSessionManager(SessionManager):

    def __init__(self, secret):
        self.secret = secret

    def exists(self, sid):
        try:
            if db.session.query(SessionData).get(sid) is not None:
                return True
            return False
        except ResourceClosedError:
            return False

    def remove(self, sid):
        # current_app.logger.debug('removing session %s' % sid)
        session = db.session.query(SessionData).get(sid)
        if session is not None:
            db.session.delete(session)
            db.session.commit()

    def new_session(self):
        sid = _generate_sid()
        db.session.add(SessionData(id=sid))
        db.session.commit()
        return ManagedSession(sid=sid)

    def get(self, sid, digest):
        """Retrieve a managed session by session-id, checking the HMAC digest"""
        session = db.session.query(SessionData).get(sid)
        if session is not None:
            randval, hmac_digest, data = session.expand_data()
        if not data:
            current_app.logger.debug('missing data?')
            return self.new_session()
        if hmac_digest != digest:
            current_app.logger.debug('Invalid HMAC for the session')
            return self.new_session()
        return ManagedSession(data, sid=sid, randval=randval, hmac_digest=hmac_digest)

    def put(self, session):
        """Store a managed session"""
        if not session.hmac_digest:
            session.sign(self.secret)
        saved_session = db.session.query(SessionData).get(session.sid)
        if saved_session is not None:
            saved_session.data = (session.randval, session.hmac_digest, dict(session))
            db.session.commit()
