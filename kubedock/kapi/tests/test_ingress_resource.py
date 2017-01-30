
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

import unittest
import mock

from kubedock.testutils.testcases import FlaskTestCase
from kubedock.testutils import create_app

from kubedock.kapi import ingress_resource


class TestCase(FlaskTestCase):
    def create_app(self):
        return create_app(self)


class TestCreateIngress(TestCase):
    domain = 'example.com'
    namespace = 'ns'
    service = 'service-2e51c3'

    @staticmethod
    def _containers(port):
        return [
            {
                'ports': [
                    port
                ]
            }
        ]

    @mock.patch.object(ingress_resource, 'create_ingress_https')
    @mock.patch.object(ingress_resource, 'create_ingress_http')
    def test_create_ingress(self, create_ingress_http_mock,
                            create_ingress_https_mock):
        # check HTTP port
        http_port = {'containerPort': 80, 'isPublic': True}
        http_containers = self._containers(http_port)
        ingress_resource.create_ingress(http_containers, self.namespace,
                                        self.domain, self.service)
        self.assertTrue(create_ingress_http_mock.called)
        self.assertFalse(create_ingress_https_mock.called)

        create_ingress_http_mock.reset_mock()

        # check HTTPS port
        https_port = {'containerPort': 443, 'isPublic': True}
        https_containers = self._containers(https_port)
        res, _ = ingress_resource.create_ingress(
            https_containers, self.namespace, self.domain, self.service)
        self.assertTrue(res)
        self.assertFalse(create_ingress_http_mock.called)
        self.assertTrue(create_ingress_https_mock.called)

        create_ingress_https_mock.reset_mock()

        # check non public port
        non_public_port = {'containerPort': 80}
        non_public_containers = self._containers(non_public_port)
        res, _ = ingress_resource.create_ingress(
            non_public_containers, self.namespace, self.domain, self.service)
        self.assertFalse(res)

        # check non HTTP(S) port
        non_http_port = {'containerPort': 81, 'isPublic': True}
        non_http_containers = self._containers(non_http_port)
        res, _ = ingress_resource.create_ingress(
            non_http_containers, self.namespace, self.domain, self.service)
        self.assertFalse(res)


if __name__ == '__main__':
    unittest.main()
