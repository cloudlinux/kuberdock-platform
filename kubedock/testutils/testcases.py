
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import logging
import os
import unittest
from json import dumps as json_dumps

import sqlalchemy
from flask_testing import TestCase as FlaskBaseTestCase
from nose.plugins.attrib import attr

from . import create_app, fixtures
from ..core import db
from ..utils import atomic


def prepareDB():
    global _db_is_ready
    if not _db_is_ready:
        meta = sqlalchemy.MetaData(bind=db.engine)
        meta.reflect()
        for tbl in reversed(meta.sorted_tables):
            db.engine.execute(tbl.delete())
        meta.drop_all()
        db.reflect()
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
    DB_HOST = os.environ.get('TEST_DB_HOST', '127.0.0.1')
    SECRET_KEY = 'testsecretkey'
    SESSION_LIFETIME = 3600
    SQLALCHEMY_DATABASE_URI = ('postgresql+psycopg2://{0}:{1}@{2}:5432/'
                               '{3}'.format(DB_USER, DB_PASSWORD,
                                            DB_HOST, DB_NAME))
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
        atomic.unregister()  # can be removed if SQLAlchemy >= 0.9.8
        atomic.register()

        # To prevent closing root transaction, start the session in a SAVEPOINT
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

        # self.app.session_interface = sessions.ManagedSessionInterface(
        #     sessions.DataBaseSessionManager(self.SECRET_KEY), 3600)
        self.app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(), self.SESSION_LIFETIME)
        acl.init_permissions()

        self.user, user_password = fixtures.user_fixtures()
        self.admin, admin_password = fixtures.admin_fixtures()
        self.userauth = (self.user.username, user_password)
        self.adminauth = (self.admin.username, admin_password)

        self.logger = logging.getLogger('APITestCase.open')
        self.logger.setLevel(logging.DEBUG)

    def open(self, url=None, method='GET', json=None, auth=None, headers=None,
             version=None, **kwargs):
        if url is None:
            url = getattr(self, 'url', '/')
        if headers is None:
            headers = {}
        if auth is not None:
            resp = self.client.open(
                '/auth/token2', method='POST',
                content_type='application/json',
                data=json_dumps({'username': auth[0], 'password': auth[1]}),
            )
            if resp.status_code != 200:
                return resp
            headers['X-Auth-Token'] = resp.json.get('token')
        if json is not None:
            kwargs.setdefault('data', json_dumps(json))
            kwargs.setdefault('content_type', 'application/json')
        if version is not None:
            headers['kuberdock-api-version'] = version
        response = self.client.open(url, method=method, headers=headers,
                                    **kwargs)
        self.logger.debug('{0}:{1}\n\t{2}\n{3}: {4}'
                          .format(url, method, json, response.status,
                                  response.data))
        return response

    def item_url(self, *args):
        return '/'.join(map(str, (self.url,) + args))

    def assertAPIError(self, response, status, type, details=None):
        if details is None:
            details = {}

        self.assertStatus(response, status)
        type_got = response.json.get('type')
        self.assertEqual(response.json.get('type'), type,
                         'Wrong response type: Expected: {exp}. Got: {got}'
                         .format(exp=type, got=type_got)
                         )
        details_got = response.json.get('details')
        self.assertEqual(details_got, details,
                         'Wrong response details: Expected: {exp}. Got: {got}'
                         .format(exp=details, got=details_got))

    def user_open(self, *args, **kwargs):
        """Open as user with permission check"""
        self.assertAPIError(self.open(*args, **dict(kwargs, auth=None)),
                            401, 'NotAuthorized')
        return self.open(*args, **dict(kwargs, auth=self.userauth))

    def admin_open(self, *args, **kwargs):
        """Open as admin with permission check"""
        self.assertAPIError(self.user_open(*args, **kwargs),
                            403, 'PermissionDenied')
        return self.open(*args, **dict(kwargs, auth=self.adminauth))


if __name__ == '__main__':
    unittest.main()
