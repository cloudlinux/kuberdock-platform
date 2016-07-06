import json
import base64
import unittest

from kubedock.testutils.testcases import APITestCase
from kubedock.testutils import fixtures


class AuthTestCase(APITestCase):
    """Authorization test case"""

    url = '/auth/token'

    def setUp(self):
        valid_user, valid_passwd = fixtures.user_fixtures(admin=True)
        blocked_user, blocked_passwd = fixtures.user_fixtures(active=False)
        deleted_user, deleted_passwd = fixtures.user_fixtures(deleted=True)
        self.valid_credentials = (valid_user.username, valid_passwd)
        self.invalid_credentials = (valid_user.username, 'bad_password')
        self.blocked_user_credentials = (blocked_user.username, blocked_passwd)
        self.deleted_user_credentials = (deleted_user.username, deleted_passwd)

    def _get_token(self, url, auth):
        return self.client.open(url, headers={
            'Authorization': 'Basic ' + base64.b64encode(':'.join(auth))})

    def test_auth_with_valid_credentials(self):
        response = self._get_token(self.url, self.valid_credentials)
        self.assert200(response)
        self.assertEqual(response.json.get('status'), 'OK')
        self.assertNotEqual(response.json.get('token'), None)

    def test_auth_case_insensitive_login(self):
        auth = (self.valid_credentials[0].swapcase(),
                self.valid_credentials[1])
        response = self._get_token(self.url, auth)
        self.assert200(response)
        self.assertEqual(response.json.get('status'), 'OK')
        self.assertNotEqual(response.json.get('token'), None)

    def test_auth_with_invalid_credentials(self):
        response = self._get_token(self.url, self.invalid_credentials)
        self.assert401(response)

    def test_auth_as_deleted_user(self):
        response = self._get_token(self.url, self.deleted_user_credentials)
        self.assert401(response)

    def test_auth_as_blocked_user(self):
        response = self._get_token(self.url, self.blocked_user_credentials)
        self.assert403(response)


class JWTTestCase(AuthTestCase):
    """Check Authorization by JWT"""

    url = '/auth/token2'

    def _get_token(self, url, auth):
        return self.client.open(
            url, data=json.dumps({'username': auth[0], 'password': auth[1]}),
            method='POST', content_type='application/json')

    # TODO: check token content for both /auth/token and /auth/token2
