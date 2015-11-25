import unittest
import base64
import os
from datetime import timedelta
from json import dumps as json_dumps

from nose.plugins.attrib import attr
from flask_sqlalchemy import SignallingSession, orm
from flask_testing import TestCase as FlaskBaseTestCase

from . import create_app, fixtures
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
        with self._transaction:
            try:
                super(DBTestCase, self).run(*args, **kwargs)
            finally:
                self._transaction.rollback()
        self._transaction.connection.invalidate()
        self._transaction.connection.close()
        self.db.session.remove()

    def _pre_setup(self, *args, **kwargs):
        super(DBTestCase, self)._pre_setup(*args, **kwargs)

        prepareDB()
        db.session.remove()

        # Create root transaction.
        connection = db.engine.connect()
        self._transaction = connection.begin()

        # Can't use just
        # db.session = db.create_scoped_session(bind=connection)
        # 'cause Flask-SQLAlchemy has a bug: it creates sessions without
        # orm.sessionmaker. See:
        # https://github.com/mitsuhiko/flask-sqlalchemy/issues/182
        # https://github.com/mitsuhiko/flask-sqlalchemy/issues/147
        class TestSignallingSession(SignallingSession):
            def __init__(self, *args, **kwargs):
                kwargs = dict(kwargs, bind=connection)
                super(TestSignallingSession, self).__init__(db, *args, **kwargs)
        db.session = orm.scoped_session(orm.sessionmaker(class_=TestSignallingSession))

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
            data = json_dumps(json)
            return self.client.open(url, method=method, data=data, headers=headers,
                                    content_type='application/json', **kwargs)

        return self.client.open(url, method=method, headers=headers, **kwargs)


if __name__ == '__main__':
    unittest.main()
