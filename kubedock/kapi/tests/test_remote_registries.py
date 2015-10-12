"""Tests for interconnection with remote registries.
Strongly depends on availability of hub.docker.com, quay.io, gcr.io.
"""
import unittest
import mock
import sys

import requests

#sys.modules['kubedock.utils'] = mock.Mock()
#sys.modules['kubedock.utils'].APIError = type('APIError', (Exception,), {})
#from ..utils import APIError

from ..images import (get_container_config, check_images_availability,
                      complement_registry, parse_image_name, get_url, APIError)
from .. import images
from ...settings import DEFAULT_REGISTRY
from ...validation import (V, args_list_schema, env_schema, path_schema,
                           port_schema, protocol_schema)
from ...testutils.testcases import DBTestCase

schema = {
    'args': dict(args_list_schema, required=True),
    'command': dict(args_list_schema, required=True),
    'env': dict(env_schema, required=True),
    'image': {'type': str, 'required': True, 'empty': False},
    'ports': {'type': list, 'required': True, 'schema': {'type': dict, 'schema': {
        'number': dict(port_schema, required=True), 'protocol': protocol_schema}}},
    'volumeMounts': {'type': list, 'required': True, 'schema': {'type': str}},
    'workingDir': path_schema,
    'secret': {'type': dict, 'schema': {
        'username': {'type': str, 'required': True, 'empty': False},
        'password': {'type': str, 'required': True, 'empty': False}}
    },
}

# Increase wait interval for login attempts to prevent tests fails on slow
# connections - when serial requests will take more time than default
# pause.
images.MIN_FAILED_LOGIN_PAUSE = 60

# Account for private repos testing. Create a new one if this will failed on
# hub.docker.com
# TODO: collect all accounts here in constants
TESTUNAME = 'wncm'
TESTPASSWORD = 'mfhhh94kw02z'


class TestGetContainerConfig(DBTestCase):
    def validate(self, data):
        validator = V()
        if not validator.validate(data, schema):
            self.fail(validator.errors)

    #@unittest.skip('')
    def test_get_container_config_3rd_party_registry_public(self):
        self.validate(get_container_config('quay.io/sergey_gruntovsky/mynginx'))

        self.validate(get_container_config('gcr.io/google_containers/etcd:2.0.9'))
        self.validate(get_container_config('gcr.io/google_containers/kube2sky:1.11'))
        self.validate(get_container_config(
            'gcr.io/google_containers/skydns:2015-03-11-001'))

    #@unittest.skip('')
    def test_get_container_config_3rd_party_registry_public_auth(self):
        self.validate(get_container_config(
            'quay.io/sergey_gruntovsky/mynginx',
            auth=('sergey_gruntovsky+kdmynginx',
                  'QH2XTHF2G3320EAD16A9WC1EV50X3UE3IP9PSFWK28JVW8OYQFI37J3AVV3KE3AZ')
        ))

    #@unittest.skip('')
    def test_get_container_config_3rd_party_registry_private(self):
        self.validate(get_container_config(
            'quay.io/sergey_gruntovsky/test_private',
            auth=('sergey_gruntovsky+kd_test_private',
                  'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY')
        ))

    #@unittest.skip('')
    def test_get_container_config_public_official(self):
        self.validate(get_container_config('nginx'))
        self.validate(get_container_config('nginx:1.9'))
        self.validate(get_container_config('debian'))

    #@unittest.skip('')
    def test_get_container_config_public(self):
        self.validate(get_container_config(TESTUNAME + '/mynginx4'))

    #@unittest.skip('')
    def test_get_container_config_private_dockerhub_repo(self):
        self.validate(get_container_config(TESTUNAME + '/test_private',
                                           auth=(TESTUNAME, TESTPASSWORD)))
        self.validate(get_container_config(TESTUNAME + '/test_private:latest',
                                           auth={'username': TESTUNAME,
                                                 'password': TESTPASSWORD}))

    #@unittest.skip('')
    def test_get_container_config_private_registry(self):
        # FIXME: what is it 45.55.52.203?
        self.validate(get_container_config('45.55.52.203:5000/mynginx',
                                           auth=(TESTUNAME, 'p-0')))


class TestMisc(DBTestCase):
    #@unittest.skip('')
    def test_parse_image_name(self):
        test_pairs = {
            'nginx': (DEFAULT_REGISTRY, 'library/nginx', 'latest'),
            TESTUNAME + '/test_private': (DEFAULT_REGISTRY, TESTUNAME + '/test_private', 'latest'),
            TESTUNAME + '/test_private:4': (DEFAULT_REGISTRY, TESTUNAME + '/test_private', '4'),
            'quay.io/sergey_gruntovsky/test_private:4':
                ('quay.io', 'sergey_gruntovsky/test_private', '4'),
            '45.55.52.203:5000/mynginx':
                ('45.55.52.203:5000', 'mynginx', 'latest'),
            '45.55.52.203:5000/mynginx:4':
                ('45.55.52.203:5000', 'mynginx', '4')
        }
        for image_name, result in test_pairs.iteritems():
            self.assertEqual(parse_image_name(image_name), result)

    #@unittest.skip('')
    def test_complement_registry(self):
        test_pairs = {'quay.io': 'https://quay.io',
                      'http://quay.io': 'http://quay.io',
                      'https://quay.io': 'https://quay.io'}
        for data, result in test_pairs.iteritems():
            self.assertEqual(complement_registry(data), result)

    #@unittest.skip('')
    def test_get_url(self):
        test_pairs = {('https://quay.io/', 'v1', 'aa', 'bb'): 'https://quay.io/v1/aa/bb'}
        for data, result in test_pairs.iteritems():
            self.assertEqual(get_url(*data), result)


# @unittest.skip('')
class TestCheckImagesAvailability(DBTestCase):
    def test_default_registry_public(self):
        check_images_availability(['nginx'])

    #@unittest.skip('TODO: dockerhub too many failed login attempts')
    def test_default_registry_private(self):

        # TODO: add valid account or replace registry server answer with
        # some kind of mocks.
        check_images_availability(['nginx', TESTUNAME + '/test_private'], [
            (TESTUNAME, TESTPASSWORD, DEFAULT_REGISTRY)
        ])

        # first failed login
        with self.assertRaises(APIError) as err:
            check_images_availability(['nginx', TESTUNAME + '/test_private'], [
                (TESTUNAME, 'wrong_password', DEFAULT_REGISTRY)
            ])
        self.assertTrue(err.exception.message.endswith('is not available'))
        failed_logins = images.PrivateRegistryFailedLogin.all()
        self.assertEqual(len(failed_logins), 1)
        failed1 = failed_logins[0]

        # second failed login
        with self.assertRaises(APIError) as err:
            # second call should return a message about waiting some seconds
            check_images_availability(['nginx', TESTUNAME + '/test_private'], [
                (TESTUNAME, 'wrong_password', DEFAULT_REGISTRY)
            ])
        self.assertEqual(err.exception.status_code,
                         requests.codes.too_many_requests)
        failed_logins = images.PrivateRegistryFailedLogin.all()
        self.assertEqual(len(failed_logins), 1)
        failed2 = failed_logins[0]
        self.assertEqual(failed1, failed2)
        self.assertEqual(failed1.login, TESTUNAME)

    #@unittest.skip('')
    def test_gcr(self):
        check_images_availability(['gcr.io/google_containers/etcd:2.0.9',
                                   'gcr.io/google_containers/kube2sky:1.11',
                                   'gcr.io/google_containers/skydns:2015-03-11-001'])

    #@unittest.skip('')
    def test_quay(self):
        check_images_availability(['quay.io/quay/redis'])
        check_images_availability(
            ['quay.io/quay/redis', 'quay.io/sergey_gruntovsky/test_private'],
            [('sergey_gruntovsky+kd_test_private',
              'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY',
              'quay.io')]
        )

        with self.assertRaises(APIError):
            check_images_availability(
                ['quay.io/quay/redis', 'quay.io/sergey_gruntovsky/test_private'],
                [('sergey_gruntovsky+kd_test_private',
                  'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY',
                  'wrong_regitry.io')]
            )

        with self.assertRaises(APIError):
            check_images_availability(
                ['quay.io/quay/redis', 'quay.io/sergey_gruntovsky/test_private'],
                [('sergey_gruntovsky+kd_test_private',
                  'wrong_password',
                  'quay.io')]
            )
        with self.assertRaises(APIError):
            check_images_availability(['quay.io/quay/redis',
                                       'quay.io/sergey_gruntovsky/test_private'])


if __name__ == '__main__':
    unittest.main()

