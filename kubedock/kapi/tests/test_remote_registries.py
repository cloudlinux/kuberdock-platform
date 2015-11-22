"""Tests for interconnection with remote registries.
Strongly depends on availability of hub.docker.com, quay.io, gcr.io.
"""
import unittest

import requests

from ..images import Image, APIError
from .. import images
from ...settings import DEFAULT_REGISTRY
from ...validation import (V, args_list_schema, env_schema, path_schema,
                           port_schema, protocol_schema)
from ...testutils.testcases import DBTestCase, attr

schema = {
    'sourceUrl': {'type': str, 'required': True},
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
images.MIN_FAILED_LOGIN_PAUSE = 120


# Accounts for repos testing. Create a new ones if these will failed on

# dockerhub account
DOCKERHUB_AUTH = DOCKERHUB_USERNAME, DOCKERHUB_PASSWORD = 'wncm', 'mfhhh94kw02z'
DOCKERHUB_PRIVATE_REPO = '{0}/test_private'.format(DOCKERHUB_USERNAME)
DOCKERHUB_PUBLIC_REPO = '{0}/mynginx4'.format(DOCKERHUB_USERNAME)
# quay account
QUAY_USERNAME = 'sergey_gruntovsky'
QUAY_ROBOT_NAME = 'sergey_gruntovsky+kd_test_private'
QUAY_ROBOT_PASSWORD = 'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY'
QUAY_ROBOT_AUTH = QUAY_ROBOT_NAME, QUAY_ROBOT_PASSWORD
QUAY_PRIVATE_REPO = 'quay.io/{0}/test_private'.format(QUAY_USERNAME)
QUAY_PUBLIC_REPO = 'quay.io/{0}/mynginx'.format(QUAY_USERNAME)
# own registry
CUSTOM_URL = '45.55.52.203:5000'
CUSTOM_USERNAME = 'wncm'
CUSTOM_PASSWORD = 'p-0'
CUSTOM_AUTH = CUSTOM_USERNAME, CUSTOM_PASSWORD
CUSTOM_PRIVATE_REPO = '{0}/mynginx'.format(CUSTOM_URL)


@attr('docker_registry')
class TestGetContainerConfig(DBTestCase):
    def validate(self, data):
        validator = V()
        if not validator.validate(data, schema):
            self.fail(validator.errors)

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_public(self):
        for image in (QUAY_PUBLIC_REPO,
                      'gcr.io/google_containers/etcd:2.0.9',
                      'gcr.io/google_containers/kube2sky:1.11',
                      'gcr.io/google_containers/skydns:2015-03-11-001'):
            self.validate(Image(image).get_container_config())

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_private(self):
        for image in (Image(QUAY_PRIVATE_REPO),
                      Image(QUAY_PRIVATE_REPO + ':latest')):
            self.validate(image.get_container_config(auth=QUAY_ROBOT_AUTH))

    # @unittest.skip('')
    def test_get_container_config_public_official(self):
        for image_url in ('nginx', 'nginx:1.9', 'debian'):
            self.validate(Image(image_url).get_container_config())

    # @unittest.skip('')
    def test_get_container_config_public(self):
        self.validate(Image(DOCKERHUB_PUBLIC_REPO).get_container_config())
        self.validate(Image(DOCKERHUB_PUBLIC_REPO + ':latest').get_container_config())

    # @unittest.skip('')
    def test_get_container_config_private_dockerhub_repo(self):
        for image in (Image(DOCKERHUB_PRIVATE_REPO),
                      Image(DOCKERHUB_PRIVATE_REPO + ':latest')):
            self.validate(image.get_container_config(auth=DOCKERHUB_AUTH))

    # @unittest.skip('')
    def test_get_container_config_private_registry(self):
        for image in (Image(CUSTOM_PRIVATE_REPO),
                      Image(CUSTOM_PRIVATE_REPO + ':latest')):
            self.validate(image.get_container_config(auth=CUSTOM_AUTH))


@attr('docker_registry')
class TestCheckImagesAvailability(DBTestCase):
    def test_default_registry_public(self):
        Image.check_images_availability(['nginx'])

    # @unittest.skip('TODO: dockerhub too many failed login attempts')
    def test_default_registry_private(self):
        Image.check_images_availability(['nginx', DOCKERHUB_PRIVATE_REPO], [
            (DOCKERHUB_USERNAME, DOCKERHUB_PASSWORD, DEFAULT_REGISTRY)
        ])

        # first failed login
        with self.assertRaises(APIError) as err:
            Image.check_images_availability(['nginx', DOCKERHUB_PRIVATE_REPO], [
                (DOCKERHUB_USERNAME, 'wrong_password', DEFAULT_REGISTRY)
            ])
        self.assertTrue(err.exception.message.endswith('is not available'))
        failed_logins = images.PrivateRegistryFailedLogin.all()
        self.assertEqual(len(failed_logins), 1)
        failed1 = failed_logins[0]

        # second failed login
        with self.assertRaises(APIError) as err:
            # second call should return a message about waiting some seconds
            Image.check_images_availability(['nginx', DOCKERHUB_PRIVATE_REPO], [
                (DOCKERHUB_USERNAME, 'wrong_password', DEFAULT_REGISTRY)
            ])
        self.assertEqual(err.exception.status_code,
                         requests.codes.too_many_requests)
        failed_logins = images.PrivateRegistryFailedLogin.all()
        self.assertEqual(len(failed_logins), 1)
        failed2 = failed_logins[0]
        self.assertEqual(failed1, failed2)
        self.assertEqual(failed1.login, DOCKERHUB_USERNAME)

    # @unittest.skip('')
    def test_gcr(self):
        Image.check_images_availability([
            'gcr.io/google_containers/etcd:2.0.9',
            'gcr.io/google_containers/kube2sky:1.11',
            'gcr.io/google_containers/skydns:2015-03-11-001',
        ])

    # @unittest.skip('')
    def test_quay(self):
        Image.check_images_availability(['quay.io/quay/redis'])
        Image.check_images_availability(
            ['quay.io/quay/redis', QUAY_PRIVATE_REPO],
            [(QUAY_ROBOT_NAME, QUAY_ROBOT_PASSWORD, 'quay.io')]
        )

        with self.assertRaises(APIError):
            Image.check_images_availability(
                ['quay.io/quay/redis', QUAY_PRIVATE_REPO],
                [(QUAY_ROBOT_NAME, QUAY_ROBOT_PASSWORD, 'wrong_regitry.io')]
            )

        with self.assertRaises(APIError):
            Image.check_images_availability(
                ['quay.io/quay/redis', QUAY_PRIVATE_REPO],
                [(QUAY_ROBOT_NAME, 'wrong_password', 'quay.io')]
            )
        with self.assertRaises(APIError):
            Image.check_images_availability(['quay.io/quay/redis', QUAY_PRIVATE_REPO])


if __name__ == '__main__':
    unittest.main()
