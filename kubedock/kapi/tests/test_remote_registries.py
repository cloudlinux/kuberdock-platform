
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

"""Tests for interconnection with remote registries.
Strongly depends on availability of hub.docker.com, quay.io, gcr.io.
"""
import os
import unittest
import urlparse

import requests
from vcr_unittest import VCRTestCase

from ..images import Image, APIError, ImageNotAvailable, CommandIsMissing
from .. import images
from ...settings import DEFAULT_REGISTRY, APP_ROOT
from ...validation import (V, args_list_schema, env_schema, path_schema,
                           port_schema, protocol_schema)
from ...testutils.testcases import DBTestCase, attr

schema = {
    'sourceUrl': {'type': 'string', 'required': True},
    'args': dict(args_list_schema, required=True),
    'command': dict(args_list_schema, required=True),
    'env': dict(env_schema, required=True),
    'image': {'type': 'string', 'required': True, 'empty': False},
    'ports': {'type': 'list', 'required': True, 'schema': {
        'type': 'dict', 'schema': {
            'number': dict(port_schema, required=True),
            'protocol': protocol_schema}}},
    'volumeMounts': {'type': 'list', 'required': True,
                     'schema': {'type': 'string'}},
    'workingDir': path_schema,
    'secret': {'type': 'dict', 'schema': {
        'username': {'type': 'string', 'required': True, 'empty': False},
        'password': {'type': 'string', 'required': True, 'empty': False}}
    },
}

# Increase wait interval for login attempts to prevent tests fails on slow
# connections - when serial requests will take more time than default
# pause.
images.MIN_FAILED_LOGIN_PAUSE = 120


# Accounts for repos testing. Create a new ones if these will failed on

# dockerhub account
DOCKERHUB_USERNAME, DOCKERHUB_PASSWORD = 'wncm', 'mfhhh94kw02z'
DOCKERHUB_AUTH = DOCKERHUB_USERNAME, DOCKERHUB_PASSWORD
DOCKERHUB_PRIVATE_REPO = '{0}/test_private'.format(DOCKERHUB_USERNAME)
DOCKERHUB_PUBLIC_REPO = '{0}/mynginx4'.format(DOCKERHUB_USERNAME)
# quay account
QUAY_USERNAME = 'sergey_gruntovsky'
QUAY_ROBOT_NAME = 'sergey_gruntovsky+kd_test_private'
QUAY_ROBOT_PASSWORD = \
    'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY'
QUAY_ROBOT_AUTH = QUAY_ROBOT_NAME, QUAY_ROBOT_PASSWORD
QUAY_PRIVATE_REPO = 'quay.io/{0}/test_private'.format(QUAY_USERNAME)
QUAY_PUBLIC_REPO = 'quay.io/{0}/mynginx'.format(QUAY_USERNAME)
# own registry
CUSTOM_URL = '45.55.52.203:5000'
CUSTOM_USERNAME = 'wncm'
CUSTOM_PASSWORD = 'p-0'
CUSTOM_AUTH = CUSTOM_USERNAME, CUSTOM_PASSWORD
CUSTOM_PRIVATE_REPO = '{0}/mynginx'.format(CUSTOM_URL)


class RemoteRegistriesTestCase(VCRTestCase, DBTestCase):
    def _get_vcr(self, **kwargs):
        my_vcr = super(RemoteRegistriesTestCase, self)._get_vcr(**kwargs)
        my_vcr.register_matcher('uri_without_qs_order',
                                self.match_uri_regardless_of_qs_order)
        my_vcr.match_on = ['uri_without_qs_order', 'host']
        return my_vcr

    def _get_cassette_library_dir(self):
        return os.path.join(APP_ROOT, "vcrpy_test_cassettes")

    def _get_cassette_name(self):
        return '{0}.{1}.{2}.yaml'.format(
            self.__module__, self.__class__.__name__, self._testMethodName)

    @staticmethod
    def match_uri_regardless_of_qs_order(r1, r2):
        def parse(url):
            r = urlparse.urlsplit(url)
            return r[0], r[1], r[2], urlparse.parse_qs(r[3]), r[4]

        return parse(r1.uri) == parse(r2.uri)


@attr('docker_registry')
class TestGetContainerConfig(RemoteRegistriesTestCase):
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
        self.validate(
            Image(DOCKERHUB_PUBLIC_REPO + ':latest').get_container_config())

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
class TestCheckContainers(RemoteRegistriesTestCase):
    def _container(self, image='i', name='n', command='c', args='a'):
        return dict({'image': image, 'name': name,
                     'command': command, 'args': args})

    def test_default_registry_public(self):
        Image.check_containers([self._container('nginx')])

    # @unittest.skip('TODO: dockerhub too many failed login attempts')
    def test_default_registry_private(self):
        Image.check_containers(
            [self._container('nginx'),
             self._container(DOCKERHUB_PRIVATE_REPO)],
            [(DOCKERHUB_USERNAME, DOCKERHUB_PASSWORD, DEFAULT_REGISTRY)])

        # first failed login
        with self.assertRaises(ImageNotAvailable) as err:
            Image.check_containers(
                [self._container('nginx'),
                 self._container(DOCKERHUB_PRIVATE_REPO)],
                [(DOCKERHUB_USERNAME, 'wrong_password', DEFAULT_REGISTRY)])
        self.assertTrue(err.exception.message.endswith('is not available'))
        failed_logins = images.PrivateRegistryFailedLogin.all()
        self.assertEqual(len(failed_logins), 1)
        failed1 = failed_logins[0]

        # second failed login
        with self.assertRaises(APIError) as err:
            # second call should return a message about waiting some seconds
            Image.check_containers(
                [self._container('nginx'),
                 self._container(DOCKERHUB_PRIVATE_REPO)],
                [(DOCKERHUB_USERNAME, 'wrong_password', DEFAULT_REGISTRY)])
        self.assertEqual(err.exception.status_code,
                         requests.codes.too_many_requests)
        failed_logins = images.PrivateRegistryFailedLogin.all()
        self.assertEqual(len(failed_logins), 1)
        failed2 = failed_logins[0]
        self.assertEqual(failed1, failed2)
        self.assertEqual(failed1.login, DOCKERHUB_USERNAME)

    def test_gcr(self):
        Image.check_containers([
            self._container('gcr.io/google_containers/etcd:2.0.9'),
            self._container('gcr.io/google_containers/kube2sky:1.11'),
            self._container('gcr.io/google_containers/skydns:2015-03-11-001'),
        ])

    def test_quay(self):
        Image.check_containers([self._container('quay.io/quay/redis')])

        containers = [self._container('quay.io/quay/redis'),
                      self._container(QUAY_PRIVATE_REPO)]
        Image.check_containers(
            containers, [(QUAY_ROBOT_NAME, QUAY_ROBOT_PASSWORD, 'quay.io')])

        with self.assertRaises(ImageNotAvailable):
            Image.check_containers(
                containers,
                [(QUAY_ROBOT_NAME, QUAY_ROBOT_PASSWORD, 'wrong_regitry.io')]
            )

        with self.assertRaises(ImageNotAvailable):
            Image.check_containers(
                containers, [(QUAY_ROBOT_NAME, 'wrong_password', 'quay.io')])
        with self.assertRaises(ImageNotAvailable):
            Image.check_containers(containers)

    def test_no_command(self):
        Image.check_containers([self._container('nginx', command=[], args=[])])
        # alpine image has no CMD nor ENTRYPOINT
        container = self._container('alpine:3.3', command=[], args=[])
        Image.check_containers([dict(container, command=['aa'], args=[])])
        Image.check_containers([dict(container, command=[], args=['aa'])])
        with self.assertRaises(CommandIsMissing):
            Image.check_containers([dict(container, command=[], args=[])])


if __name__ == '__main__':
    unittest.main()
