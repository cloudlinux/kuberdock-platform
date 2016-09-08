import unittest

import mock

from kubedock.testutils.testcases import APITestCase
from kubedock.validation import V

response_validator = V({
    'status': {'type': 'string', 'required': True, 'allowed': ['OK', 'error']},
    'data': {'type': 'dict', 'required': True, 'schema': {
        'id': {'type': 'integer', 'required': True},
        'user_id': {'type': 'integer', 'required': True},
        'name': {'type': 'string', 'required': True},
        'template': {'type': 'string', 'required': True}}}})


class PredefinedAppsTestCase(APITestCase):
    """Tests for /api/predefined-apps endpoint"""
    url = '/predefined-apps'

    def setUp(self):
        self.name = 'test yaml app'
        self.template = 'test yaml app template'

    def test_get_user(self):
        self._test_get(self.userauth)

    def test_get_admin(self):
        self._test_get(self.adminauth)

    def _test_get(self, auth):
        self.admin_open(method='POST',
                        json={'name': self.name, 'template': self.template})

        # get list
        response = self.open(auth=auth)
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data'][0]
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

        # get by id
        url = self.item_url(predefined_app['id'])
        response = self.open(url, auth=auth)
        self.assert200(response)
        template_list = response.json['data'].pop('templates')
        predefined_app.pop('templates')
        self.assertEqual(predefined_app, response.json['data'])

        # get by id, file-only
        response = self.open(url, query_string={'file-only': True},
                             auth=auth)
        self.assert200(response)
        # raw response data
        self.assertEqual(predefined_app['template'], response.data)
        self.assertEqual('application/x-yaml',
                         response.headers.get('Content-Type'))

        # get by id with version
        url = self.item_url(predefined_app['id'], template_list[0]['id'])
        response = self.open(url, auth=auth)
        self.assert200(response)
        predefined_app.pop('templates', None)  # remove template versions
        self.assertEqual(predefined_app, response.json['data'])

        # get by id with version, file-only
        response = self.open(url, query_string={'file-only': True},
                             auth=auth)
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
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

    def test_post_new_version_as_json(self):
        self.admin_open(method='POST',
                        json={'name': self.name, 'template': self.template})

        response = self.open(auth=self.adminauth)
        self.assert200(response)
        predefined_app = response.json['data'][0]

        url = self.item_url(predefined_app['id'])
        # post as json with id
        response = self.admin_open(url, method='POST',
                                   json={'name': self.name,
                                         'template': self.template})
        self.assert200(response)
        response_validator.validate(response.json)

        response = self.open(url, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data']['templates']
        self.assertEqual(len(template_list), 2)

    def test_post_as_file(self):
        # post as file-only
        response = self.admin_open(
            method='POST', content_type='multipart/form-data', buffered=True,
            data={'name': self.name, 'template': self.template}
        )
        self.assert200(response)
        response_validator.validate(response.json)
        predefined_app = response.json['data']
        self.assertEqual(predefined_app['name'], self.name)
        self.assertEqual(predefined_app['template'], self.template)

    def test_put(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name,
                                 'template': self.template},
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

    def test_put_version(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name,
                                 'template': self.template},
        ).json['data']

        url_app = self.item_url(predefined_app['id'])
        # post as json with id
        response = self.admin_open(url_app, method='POST',
                                   json={'name': self.name,
                                         'template': self.template})
        self.assert200(response)
        response_validator.validate(response.json)

        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data']['templates']
        # get second template
        url_app_ver = self.item_url(predefined_app['id'],
                                    template_list[1]['id'])

        # update template
        new_app = {'name': 'updated yaml template name',
                   'template': 'updated yaml template'}
        response = self.admin_open(url_app_ver, method='PUT', json=new_app)
        self.assert200(response)
        response_validator.validate(response.json)

        # get by id (all templates)
        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data'].pop('templates')

        self.assertEqual(new_app['name'], response.json['data']['name'])
        self.assertEqual(new_app['template'], template_list[1]['template'])
        self.assertFalse(template_list[0]['active'])
        self.assertTrue(template_list[1]['active'])
        self.assertEqual(self.template, template_list[0]['template'])

    def test_delete(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name,
                                 'template': self.template},
        ).json['data']

        # delete template
        url = self.item_url(predefined_app['id'])
        response = self.admin_open(url, method='DELETE')
        self.assert200(response)
        self.assert404(self.open(url, auth=self.adminauth))

    def test_delete_version(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name,
                                 'template': self.template},
        ).json['data']

        url_app = self.item_url(predefined_app['id'])
        # post as json with id
        response = self.admin_open(url_app, method='POST',
                                   json={'name': self.name,
                                         'template': self.template})
        self.assert200(response)
        response_validator.validate(response.json)

        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data']['templates']
        # get second template
        url_app_ver = self.item_url(predefined_app['id'],
                                    template_list[1]['id'])

        # delete template
        response = self.admin_open(url_app_ver, method='DELETE')
        self.assert200(response)
        response_validator.validate(response.json)

        # get by id (all templates)
        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data'].pop('templates')

        self.assertEqual(len(template_list), 1)
        self.assertTrue(template_list[0]['active'])

    @mock.patch('kubedock.api.predefined_apps.PredefinedApp.validate')
    def test_validate_template(self, v):
        url = '{0}/validate-template'.format(self.url)
        response = self.admin_open(url, method='POST',
                                   json={'template': self.template})
        self.assert200(response)
        v.assert_called_once_with(self.template)

    def test_set_active_version(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name,
                                 'template': self.template},
        ).json['data']

        url_app = self.item_url(predefined_app['id'])
        # post as json with id
        response = self.admin_open(url_app, method='POST',
                                   json={'name': self.name,
                                         'template': self.template})
        self.assert200(response)
        response_validator.validate(response.json)

        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data']['templates']

        # get first template
        url_app_ver = self.item_url(predefined_app['id'],
                                    template_list[0]['id'])

        # set active
        new_app = {'active': True}
        response = self.admin_open(url_app_ver, method='PUT', json=new_app)
        self.assert200(response)
        response_validator.validate(response.json)

        # get by id (all templates)
        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data'].pop('templates')

        self.assertFalse(template_list[0]['active'])
        self.assertTrue(template_list[1]['active'])

    def test_set_switchingPackagesAllowed(self):
        predefined_app = self.admin_open(
            method='POST', json={'name': self.name,
                                 'template': self.template},
        ).json['data']

        url_app = self.item_url(predefined_app['id'])

        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data']['templates']

        self.assertEqual(len(template_list), 1)

        # post as json with id
        response = self.admin_open(url_app, method='POST',
                                   json={'name': self.name,
                                         'template': self.template,
                                         'switchingPackagesAllowed': True})
        self.assert200(response)
        response_validator.validate(response.json)

        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data']['templates']

        self.assertEqual(len(template_list), 2)

        self.assertFalse(template_list[0]['switchingPackagesAllowed'])
        self.assertTrue(template_list[1]['switchingPackagesAllowed'])

        # get first template
        url_app_ver1 = self.item_url(predefined_app['id'],
                                     template_list[0]['id'])

        url_app_ver2 = self.item_url(predefined_app['id'],
                                     template_list[1]['id'])

        # set switchingPackagesAllowed
        new_app = {'switchingPackagesAllowed': True}
        response = self.admin_open(url_app_ver1, method='PUT', json=new_app)
        self.assert200(response)
        response_validator.validate(response.json)

        # reset switchingPackagesAllowed
        new_app = {'switchingPackagesAllowed': False}
        response = self.admin_open(url_app_ver2, method='PUT', json=new_app)
        self.assert200(response)
        response_validator.validate(response.json)

        # get by id (all templates)
        response = self.open(url_app, auth=self.adminauth)
        self.assert200(response)
        template_list = response.json['data'].pop('templates')

        self.assertEqual(len(template_list), 2)

        self.assertTrue(template_list[0]['switchingPackagesAllowed'])
        self.assertFalse(template_list[1]['switchingPackagesAllowed'])


if __name__ == '__main__':
    unittest.main()
