import unittest

import etcd
import mock

from kubedock.testutils.testcases import APITestCase


class FakeRestrictedPort(object):

    def __init__(self, port, protocol):
        self.port = port
        self.protocol = protocol

    def dict(self):
        return {'port': self.port, 'protocol': self.protocol}


class TestRestrictedPorts(APITestCase):
    ports = [
        {
            'port': 25,
            'protocol': 'tcp',
        },
        {
            'port': 53,
            'protocol': 'udp',
        },
    ]
    kuberdock_nodes_tier = [FakeRestrictedPort(**port) for port in ports]
    url = '/restricted-ports'

    @mock.patch('kubedock.kapi.restricted_ports.RestrictedPort')
    def test_get_ports(self, restricted_port_mock):
        restricted_port_mock.query = self.kuberdock_nodes_tier
        response = self.admin_open()
        self.assert200(response)
        self.assertEqual(response.json['data'], self.ports)

    @mock.patch('kubedock.kapi.restricted_ports.db')
    @mock.patch('kubedock.kapi.restricted_ports.RestrictedPort')
    @mock.patch('kubedock.kapi.restricted_ports.etcd.Client')
    def test_set_port(self, etcd_client_mock, restricted_port_mock, db_mock):
        response = self.admin_open(method='POST')
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'protocol': u'required field',
                             u'port': u'required field'})

        response = self.admin_open(method='POST',
                                   json={'port': '8000', 'protocol': 'tcp'})
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'port': u'must be of integer type'})

        response = self.admin_open(method='POST',
                                   json={'port': 0, 'protocol': 'tcp'})
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'port': u'min value is 1'})

        response = self.admin_open(method='POST',
                                   json={'port': 65536, 'protocol': 'tcp'})
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'port': u'max value is 65535'})

        response = self.admin_open(method='POST',
                                   json={'port': 8000, 'protocol': '!WRONG!'})
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'protocol': u'unallowed value !WRONG!'})

        response = self.admin_open(method='POST',
                                   json={'port': 8000, 'protocol': 'tcp'})
        self.assertAPIError(response, 400,
                            'RestrictedPortsException.ClosePortError',
                            {u'message': u'Port already closed'})

        restricted_port_mock.query.filter_by.return_value.first.return_value = \
            None
        response = self.admin_open(method='POST',
                                   json={'port': 8002, 'protocol': 'tcp'})

        self.assert200(response)
        self.assertEqual(db_mock.session.add.call_count, 1)

        etcd_client_mock.return_value.read.side_effect = \
            etcd.EtcdException('!!!')
        response = self.admin_open(method='POST',
                                   json={'port': 8002, 'protocol': 'tcp'})
        self.assertAPIError(
            response,
            400,
            'RestrictedPortsException.ClosePortError',
            {u'message': u"Can't update restricted port policy in etcd"},
        )

    @mock.patch('kubedock.kapi.restricted_ports.db')
    @mock.patch('kubedock.kapi.restricted_ports.RestrictedPort')
    @mock.patch('kubedock.kapi.restricted_ports.etcd.Client')
    def test_del_port(self, etcd_client_mock, restricted_port_mock, db_mock):
        with self.assertRaises(AssertionError) as context:
            self.admin_open(self.item_url('wrong-port-number', 'tcp'),
                            method='DELETE')
            self.assertEqual('HTTP Status 401 expected but got 404',
                             context.exception)

        response = self.admin_open(self.item_url('0', 'tcp'),
                                   method='DELETE')
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'port': u'min value is 1'})

        response = self.admin_open(self.item_url('65536', 'tcp'),
                                   method='DELETE')
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'port': u'max value is 65535'})

        response = self.admin_open(self.item_url('8000', '!WRONG!'),
                                   method='DELETE')
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'protocol': u'unallowed value !WRONG!'})

        restricted_port_mock.query.filter_by.return_value.first.return_value = \
            None
        response = self.admin_open(self.item_url('8000', 'tcp'),
                                   method='DELETE')
        self.assertAPIError(response, 400,
                            'RestrictedPortsException.OpenPortError',
                            {u'message': u"Port doesn't closed"})

        restricted_port_mock.query.filter_by.return_value.first.return_value = \
            self.ports[0]
        response = self.admin_open(self.item_url('8000', 'tcp'),
                                   method='DELETE')
        self.assert200(response)
        self.assertEqual(db_mock.session.delete.call_count, 1)

        etcd_client_mock.return_value.delete.side_effect = \
            etcd.EtcdException('!!!')
        response = self.admin_open(self.item_url('8000', 'tcp'),
                                   method='DELETE')
        self.assertAPIError(
            response,
            400,
            'RestrictedPortsException.OpenPortError',
            {u'message': u"Can't remove restricted ports policy from etcd"},
        )


if __name__ == '__main__':
    unittest.main()
