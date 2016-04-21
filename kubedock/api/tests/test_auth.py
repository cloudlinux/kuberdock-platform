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

    def test_auth_with_valid_credentials(self):
        response = self.open(url=self.url, auth=self.valid_credentials)
        self.assert200(response)
        self.assertEqual(response.json.get('status'), 'OK')
        self.assertNotEqual(response.json.get('token'), None)

    def test_auth_with_invalid_credentials(self):
        response = self.open(url=self.url, auth=self.invalid_credentials)
        self.assert401(response)

    def test_auth_as_deleted_user(self):
        response = self.open(url=self.url, auth=self.deleted_user_credentials)
        self.assert401(response)

    def test_auth_as_blocked_user(self):
        response = self.open(url=self.url, auth=self.blocked_user_credentials)
        self.assert403(response)
