import unittest
import base64
from json import dumps as json_dumps

from flask_testing import TestCase as FlaskBaseTestCase

from . import create_app, fixtures
from kubedock.core import db


# TestCases


TestCase = unittest.TestCase


class FlaskTestCase(FlaskBaseTestCase):
    TESTING = True
    PRESERVE_CONTEXT_ON_EXCEPTION = False
    LOGIN_DISABLED = False


class DBTestCase(FlaskTestCase):
    DB_ENGINE = 'postgresql+psycopg2'
    DB_USER = 'kuberdock'
    DB_PASSWORD = 'kuberdock2go'
    DB_NAME = 'testkuberdock'
    SECRET_KEY = 'testsecretkey'
    SQLALCHEMY_DATABASE_URI = ('postgresql+psycopg2://{0}:{1}@127.0.0.1:5432/'
                               '{2}'.format(DB_USER, DB_PASSWORD, DB_NAME))

    def create_app(self):
        create_app(self)

    def setUp(self):
        db.reflect()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()


class APITestCase(DBTestCase):
    def create_app(self):
        from kubedock.api import create_app
        return create_app(self)

    def setUp(self):
        super(APITestCase, self).setUp()
        fixtures.initial_fixtures()

        from kubedock.rbac import acl
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
