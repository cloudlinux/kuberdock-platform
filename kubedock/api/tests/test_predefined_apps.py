import mock
import unittest
from kubedock.testutils.testcases import APITestCase

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
        self.name = 'test yaml app'
        self.template = 'test yaml app template'

    def test_get(self):
        self.admin_open(method='POST',
                        json={'name': self.name, 'template': self.template})
        # get list
        response = self.admin_open()
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data'][0]
        self.assertEqual(predefined_app['user_id'], self.admin.id)
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

        # get by id
        url = self.item_url(predefined_app['id'])
        response = self.admin_open(url)
        self.assert200(response)
        self.assertEqual(predefined_app, response.json['data'])

        # get by id, file-only
        response = self.admin_open(url, query_string={'file-only': True})
        self.assert200(response)
        # raw response data
        self.assertEqual(predefined_app['template'], response.data)
        self.assertEqual('application/x-yaml',
                         response.headers.get('Content-Type'))

    def test_post_as_json(self):
        # post as json
        response = self.admin_open(method='POST',
                                   json={'name': self.name,
                                         'template': self.template})
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data']
        self.assertEqual(predefined_app['user_id'], self.admin.id)
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

    def test_post_as_file(self):
        # post as file-only
        response = self.admin_open(
            method='POST', content_type='multipart/form-data', buffered=True,
            data={'name': self.name, 'template': self.template}
        )
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data']
        self.assertEqual(predefined_app['user_id'], self.admin.id)
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

    def test_put(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name, 'template': self.template},
        ).json['data']

        # update template
        new_app = {'name': 'updated yaml template name',
                   'template': 'updated yaml template'}
        url = self.item_url(predefined_app['id'])
        response = self.admin_open(url, method='PUT', json=new_app)
        self.assert200(response)
        response_validator.validate(response.json)
        updated_predefined_app = response.json['data']
        self.assertDictContainsSubset(new_app, updated_predefined_app)
        self.assertEqual(predefined_app['id'], updated_predefined_app['id'])
        self.assertEqual(predefined_app['user_id'],
                         updated_predefined_app['user_id'])

    def test_delete(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name, 'template': self.template},
        ).json['data']

        # update template
        url = self.item_url(predefined_app['id'])
        response = self.admin_open(url, method='DELETE')
        self.assert200(response)
        self.assert404(self.admin_open(url))

    @mock.patch('kubedock.api.predefined_apps.kapi_apps')
    def test_validate_template(self, kapi_apps):
        url = '{0}/validate-template'.format(self.url)
        response = self.admin_open(url, method='POST',
                                   json={'template': self.template})
        self.assert200(response)
        kapi_apps.validate_template.assert_called_once_with(self.template)


if __name__ == '__main__':
    unittest.main()
