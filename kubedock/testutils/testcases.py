import unittest
import base64
import os
import logging
from datetime import timedelta
from json import dumps as json_dumps

from nose.plugins.attrib import attr
from flask_testing import TestCase as FlaskBaseTestCase

from . import create_app, fixtures
from kubedock import utils
from kubedock.core import db


def prepareDB():
    global _db_is_ready
    if not _db_is_ready:
        db.reflect()
        db.drop_all()
        db.create_all()
        fixtures.initial_fixtures()
        db.session.commit()
        _db_is_ready = True
_db_is_ready = bool(os.getenv('DB_IS_READY', False))


TestCase = unittest.TestCase


class FlaskTestCase(FlaskBaseTestCase):
    TESTING = True
    PRESERVE_CONTEXT_ON_EXCEPTION = False
    LOGIN_DISABLED = False


@attr('db')
class DBTestCase(FlaskTestCase):
    DB_ENGINE = 'postgresql+psycopg2'
    DB_USER = 'kuberdock'
    DB_PASSWORD = 'kuberdock2go'
    DB_NAME = 'testkuberdock'
    SECRET_KEY = 'testsecretkey'
    SQLALCHEMY_DATABASE_URI = ('postgresql+psycopg2://{0}:{1}@127.0.0.1:5432/'
                               '{2}'.format(DB_USER, DB_PASSWORD, DB_NAME))
    fixtures = fixtures

    def create_app(self):
        return create_app(self)

    def run(self, *args, **kwargs):
        try:
            super(DBTestCase, self).run(*args, **kwargs)
        finally:
            self._transaction.rollback()
        self._transaction.connection.invalidate()
        self._transaction.connection.close()
        self.db.session.remove()
        self.db.engine.dispose()

    def _pre_setup(self, *args, **kwargs):
        super(DBTestCase, self)._pre_setup(*args, **kwargs)

        prepareDB()
        db.session.remove()

        # Create root transaction.
        connection = db.engine.connect()
        self._transaction = connection.begin()

        db.session = db.create_scoped_session({'bind': connection})
        utils.atomic.unregister()  # can be removed if SQLAlchemy >= 0.9.8
        utils.atomic.register()

        # To prevent closing root transaction, start the session in a SAVEPOINT...
        db.session.begin_nested()

        # and each time that SAVEPOINT ends, reopen it
        @db.event.listens_for(db.session, 'after_transaction_end')
        def restart_savepoint(session, transaction):
            if transaction.nested and not transaction._parent.nested:
                # ensure that state is expired the way
                # session.commit() at the top level normally does
                session.expire_all()
                session.begin_nested()

        self.db = db


class APITestCase(DBTestCase):
    def create_app(self):
        from kubedock.api import create_app
        return create_app(self, fake_sessions=True)

    def _pre_setup(self, *args, **kwargs):
        super(APITestCase, self)._pre_setup(*args, **kwargs)
        from kubedock import sessions
        from kubedock.rbac import acl

        self.app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(self.SECRET_KEY), [], timedelta(days=1))
        acl.init_permissions()

        self.user, user_password = fixtures.user_fixtures()
        self.admin, admin_password = fixtures.admin_fixtures()
        self.userauth = (self.user.username, user_password)
        self.adminauth = (self.admin.username, admin_password)

        self.logger = logging.getLogger('APITestCase.open')
        self.logger.setLevel(logging.DEBUG)

    def open(self, url=None, method='GET', json=None, auth=None, headers=None, **kwargs):
        if url is None:
            url = getattr(self, 'url', '/')
        if headers is None:
            headers = {}
        if auth is not None:
            headers['Authorization'] = 'Basic ' + base64.b64encode(
                '{0}:{1}'.format(*auth)
            )
        if json is not None:
            kwargs.setdefault('data', json_dumps(json))
            kwargs.setdefault('content_type', 'application/json')
        response = self.client.open(url, method=method, headers=headers, **kwargs)
        self.logger.debug('{0}:{1}\n\t{2}\n{3}: {4}'
                          .format(url, method, json, response.status, response.data))
        return response

    def item_url(self, *args):
        return '/'.join(map(str, (self.url,) + args))

    def assertAPIError(self, response, status, type):
        self.assertStatus(response, status)
        msg = 'Wrong response: {0} expected. Got: {1}'.format(type, response.json)
        self.assertEqual(response.json.get('type'), type, msg)

    def admin_open(self, *args, **kwargs):
        """Open as admin with permission check"""
        self.assertAPIError(self.open(*args, **dict(kwargs, auth=None)),
                            401, 'NotAuthorized')
        self.assertAPIError(self.open(*args, **dict(kwargs, auth=self.userauth)),
                            403, 'PermissionDenied')
        return self.open(*args, **dict(kwargs, auth=self.adminauth))


if __name__ == '__main__':
    unittest.main()
