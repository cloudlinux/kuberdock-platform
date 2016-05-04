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
from .users.models import SessionData, User
from .core import db
from .login import process_jwt, make_session


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
    def __init__(self, initial=None, sid=None, new=False):
        def on_update(self):
            self.modified = True

        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.new = new
        self.modified = False
        #self.randval = randval
        #self.hmac_digest = hmac_digest

    #def sign(self, secret):
    #    if not self.hmac_digest:
    #        self.randval = ''.join(random.sample(
    #            string.lowercase+string.digits, 20))
    #        self.hmac_digest = _calc_hmac('%s:%s' % (self.sid, self.randval),
    #                                      secret)


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
        if not token:
            return self.manager.new_session()
        current_app.logger.debug(token)
        data = process_jwt(token, False)
        if data is None:
            print 'open_session deleting token: {0}'.format(token)
            self.manager.remove(token=token)
            return self.manager.new_session()
        return self.manager.get(data)

    def save_session(self, app, session, response):
        if not session:
            self.manager.remove(sid=session.sid)
            return
        if not session.modified:
            return
        user = User.query.get(int(session.get('user_id')))
        token = make_session(user, expire=self.time_delta)
        response.headers['X-Auth-Token'] = token
        self.manager.put(session, token)
        session.modified = False


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

    def remove(self, sid=None, token=None):
        if not sid and not token:
            return
        if sid:
            session = db.session.query(SessionData).get(sid)
        elif token:
            session = db.session.query(SessionData).filter_by(token=token).first()
        if session is not None:
            db.session.delete(session)
            db.session.commit()

    def new_session(self):
        sid = _generate_sid()
        db.session.add(SessionData(id=sid))
        db.session.commit()
        return ManagedSession(sid=sid)

    def get(self, data):
        _valid_fields = ('sid', '_fresh', 'user_id', '_id')
        return ManagedSession(dict((k, v) for k, v in data.items()
            if k in _valid_fields))

    def put(self, session, token):
        """Store a managed session"""
        if session.sid is None or token is None:
            return
        saved_session = db.session.query(SessionData).get(session.sid)
        if saved_session is None:
            return
        saved_session.token = token
        db.session.commit()
