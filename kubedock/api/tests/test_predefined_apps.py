import unittest
from kubedock.testutils.testcases import APITestCase
from kubedock.testutils import fixtures

from StringIO import StringIO
from kubedock.validation import V


response_validator = V({
    'status': {'type': str, 'required': True, 'allowed': ['OK', 'error']},
    'data': {'type': dict, 'required': True, 'schema': {
        'id': {'type': int, 'required': True},
        'user_id': {'type': int, 'required': True},
        'name': {'type': str, 'required': True},
        'template': {'type': str, 'required': True}}}})


class PredefinedAppsTestCase(APITestCase):
    """Tests for /api/predefined-apps endpoint"""
    url = '/predefined-apps'

    def setUp(self):
        super(PredefinedAppsTestCase, self).setUp()
        self.admin, admin_password = fixtures.admin_fixtures()
        self.adminauth = (self.admin.username, admin_password)
        self.name = 'test yaml app'
        self.template = 'test yaml app template'

    # @unittest.skip('')
    def test_get(self):
        self.open(method='POST',
                  json={'name': self.name, 'template': self.template},
                  auth=self.adminauth)
        # get list
        response = self.open(auth=self.adminauth)
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data'][0]
        self.assertEqual(predefined_app['user_id'], self.admin.id)
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

        # get by id
        url = '{0}/{1}'.format(self.url, predefined_app['id'])
        response = self.open(url, auth=self.adminauth)
        self.assert200(response)
        self.assertEqual(predefined_app, response.json['data'])

        # get by id, file-only
        url += '?file-only=true'
        response = self.open(url, auth=self.adminauth)
        self.assert200(response)
        # raw response data
        self.assertEqual(predefined_app['template'], response.data)
        self.assertEqual('application/x-yaml',
                         response.headers.get('Content-Type'))

    # @unittest.skip('')
    def test_post_as_json(self):
        # post as json
        response = self.open(method='POST',
                             json={'name': self.name,
                                   'template': self.template},
                             auth=self.adminauth)
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data']
        self.assertEqual(predefined_app['user_id'], self.admin.id)
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

    # @unittest.skip('')
    def test_post_as_file(self):
        # post as file-only
        response = self.open(
            method='POST', auth=self.adminauth,
            content_type='multipart/form-data', buffered=True,
            data={'name': self.name,
                  'template': (StringIO(self.template), 'my_app.yaml')}
        )
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data']
        self.assertEqual(predefined_app['user_id'], self.admin.id)
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

    # @unittest.skip('')
    def test_put(self):
        predefined_app = self.open(
            method='POST', json={'name': self.name, 'template': self.template},
            auth=self.adminauth
        ).json['data']

        # update template
        new_app = {'name': 'updated yaml template name',
                   'template': 'updated yaml template'}
        url = '{0}/{1}'.format(self.url, predefined_app['id'])
        response = self.open(url, method='PUT', json=new_app,
                             auth=self.adminauth)
        self.assert200(response)
        response_validator.validate(response.json)
        updated_predefined_app = response.json['data']
        self.assertDictContainsSubset(new_app, updated_predefined_app)
        self.assertEqual(predefined_app['id'], updated_predefined_app['id'])
        self.assertEqual(predefined_app['user_id'],
                         updated_predefined_app['user_id'])

    # @unittest.skip('')
    def test_delete(self):
        predefined_app = self.open(
            method='POST', json={'name': self.name, 'template': self.template},
            auth=self.adminauth
        ).json['data']

        # update template
        url = '{0}/{1}'.format(self.url, predefined_app['id'])
        response = self.open(url, method='DELETE', auth=self.adminauth)
        self.assert200(response)
        self.assert404(self.open(url, auth=self.adminauth))


if __name__ == '__main__':
    unittest.main()
