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
