"""Unit tests for kapi.ippool
"""
import unittest

import mock
import ipaddress
import responses

from kubedock.core import db
from kubedock.exceptions import APIError
from kubedock.kapi import ippool
from kubedock.pods.models import IPPool
from kubedock.testutils.fixtures import K8SAPIStubs
from kubedock.testutils.testcases import DBTestCase
from kubedock.kapi.node import Node as K8SNode, \
    NodeExceptionNegativeFreeIPCount
from kubedock.testutils.testcases import attr
from flask import current_app


@attr('db')
class TestIpPool(DBTestCase):
    """Tests for ippool.IpAddrPool class"""

    def setUp(self):
        super(TestIpPool, self).setUp()
        self.node = self.fixtures.node()
        self.db.session.add(self.node)
        self.db.session.commit()

        self.stubs = K8SAPIStubs()
        self.stubs.node_info_in_k8s_api(self.node.hostname)
        self.stubs.node_info_update_in_k8s_api(self.node.hostname)

        current_app.config['NONFLOATING_PUBLIC_IPS'] = True

    def test_get_returns_emtpy_list_by_default(self):
        res = ippool.IpAddrPool().get()
        self.assertEqual(res, [])

    def test_get_returns_none_if_network_does_not_exist(self):
        res = ippool.IpAddrPool().get(net='somegarbage')
        self.assertIsNone(res)

    def test_add_raises_if_pool_network_is_incorrect(self):
        pool = IPPool(network='somegarbage')
        db.session.add(pool)
        db.session.commit()
        with self.assertRaises(ValueError):
            ippool.IpAddrPool().get()

    def test_add_successfully_adds_network(self):
        pool = IPPool(network='192.168.1.1/32')
        db.session.add(pool)
        db.session.commit()
        res = ippool.IpAddrPool().get()
        first_net = {
            'allocation': [('192.168.1.1', None, 'free')],
            'blocked_list': [],
            'free_hosts': ['192.168.1.1'],
            'id': u'192.168.1.1/32',
            'ipv6': False,
            'network': u'192.168.1.1/32',
            'node': None,
            'page': 1,
            'pages': 1,
        }
        self.assertEqual(res, [first_net])
        pool = IPPool(network='192.168.1.2/32')
        db.session.add(pool)
        db.session.commit()
        res = ippool.IpAddrPool().get()
        self.assertEqual(len(res), 2)

        res = ippool.IpAddrPool().get(net='192.168.1.3/32')
        self.assertIsNone(res)

        res = ippool.IpAddrPool().get(net='192.168.1.1/32')
        self.assertEqual(res, first_net)

        res = ippool.IpAddrPool().get(net='192.168.1.1/32', page=1000)
        self.assertEqual(res, first_net)

    def test_get_free_host_returns_none_when_there_are_no_ips(self):
        res = ippool.IpAddrPool().get_free()
        self.assertIsNone(res)

    def test_get_free_host_returns_first_ip_of_a_net_if_all_are_free(self):
        pool = IPPool(network='192.168.1.0/24')
        db.session.add(pool)
        db.session.commit()
        res = ippool.IpAddrPool().get_free()
        self.assertEqual(res, '192.168.1.0')

    def test_create_raises_if_given_data_is_invalid(self):
        for invalid in (None, {}):
            with self.assertRaises(APIError):
                ippool.IpAddrPool().create(invalid)

    def test_cant_add_overlapping_network(self):
        current_app.config['NONFLOATING_PUBLIC_IPS'] = False
        # 192.168.0.9 - 192.168.0.10
        ippool.IpAddrPool().create({'network': u'192.168.1.8/30'})

        with self.assertRaisesRegexp(APIError, 'overlaps'):
            ippool.IpAddrPool().create({'network': u'192.168.1.9/32'})

        with self.assertRaisesRegexp(APIError, 'overlaps'):
            ippool.IpAddrPool().create({'network': u'192.168.1.0/24'})

        with self.assertRaisesRegexp(APIError, 'overlaps'):
            ippool.IpAddrPool().create({'network': u'192.168.0.0/16'})

    @responses.activate
    def test_create_successfully_creates_network_instance(self):
        data = {
            'network': u'192.168.1.1/32',
            'node': self.node.hostname,
        }
        res = ippool.IpAddrPool().create(data)
        self.assertEqual(res, {'network': data['network'],
                               'free_hosts': ['192.168.1.1'],
                               'blocked_list': [],
                               'ipv6': False,
                               'pages': 1, 'page': 1,
                               'id': data['network'],
                               'allocation': [('192.168.1.1', None, 'free')],
                               'node': data['node']})

    @responses.activate
    def test_create_correctly_excludes_blocks(self):
        pool = IPPool(network='192.168.1.1/32')
        db.session.add(pool)
        db.session.commit()

        expected_block_ips = [
            u'192.168.2.1', u'192.168.2.3', u'192.168.2.4',
            u'192.168.2.5', u'192.168.2.7'
        ]

        block = '192.168.2.1,192.168.2.3-192.168.2.5,192.168.2.7'

        data = {
            'network': u'192.168.2.0/24',
            'autoblock': block,
            'node': self.node.hostname,
        }
        res = ippool.IpAddrPool().create(data)
        self.assertEqual({
            'network': res['network'],
            'blocked_list': res['blocked_list']
        }, {
            'network': data['network'],
            'blocked_list': expected_block_ips,
        })

        invalid_block = 'qwerty'
        data = {
            'network': '192.168.4.0/24',
            'autoblock': invalid_block
        }
        with self.assertRaises(APIError):
            ippool.IpAddrPool().create(data)

        networks = db.session.query(IPPool).order_by(IPPool.network)
        self.assertEqual(
            [item.network for item in networks],
            [u'192.168.1.1/32', u'192.168.2.0/24'],
        )

    @responses.activate
    @mock.patch.object(ippool.PodCollection, '_remove_public_ip')
    def test_update(self, remove_public_mock):
        """Test IpAddrPool.update method."""
        network = u'192.168.2.0/24'
        with self.assertRaises(APIError):
            ippool.IpAddrPool().update(network, None)

        pool = IPPool(network='192.168.1.0/24')
        node = self.node

        db.session.add(pool)
        db.session.commit()

        block = '192.168.2.1,192.168.2.3-192.168.2.5,192.168.2.7'
        data = {
            'network': network,
            'autoblock': block,
            'node': node.hostname,
        }
        ippool.IpAddrPool().create(data)

        res1 = ippool.IpAddrPool().update(network, None)
        self.assertIsNotNone(res1)
        self.assertEqual(res1['network'], network)

        # add already blocked ip
        block_ip = u'192.168.2.1'
        params = {'block_ip': block_ip}
        with self.assertRaises(APIError):
            ippool.IpAddrPool().update(network, params)

        # block new ip
        block_ip1 = u'192.168.2.111'
        params = {'block_ip': block_ip1}
        res = ippool.IpAddrPool().update(network, params)
        self.assertEqual(
            set(res['blocked_list']),
            set(res1['blocked_list']) | {block_ip1}
        )

        # and one else
        block_ip2 = u'192.168.2.112'
        params = {'block_ip': block_ip2}
        res = ippool.IpAddrPool().update(network, params)
        self.assertEqual(
            set(res['blocked_list']),
            set(res1['blocked_list']) | {block_ip1, block_ip2}
        )

        unblock_ip = block_ip1
        params = {'unblock_ip': unblock_ip}
        res = ippool.IpAddrPool().update(network, params)
        self.assertEqual(
            set(res['blocked_list']),
            set(res1['blocked_list']) | {block_ip2}
        )

        self.assertFalse(remove_public_mock.called)

        unbind_ip = '192.168.2.222'
        params = {'unbind_ip': unbind_ip}
        res = ippool.IpAddrPool().update(network, params)
        self.assertEqual(
            set(res['blocked_list']),
            set(res1['blocked_list']) | {block_ip2}
        )
        remove_public_mock.assert_called_once_with(ip=unbind_ip)

        res = ippool.IpAddrPool().update(network, {'node': node.hostname})
        self.assertEqual(res['node'], node.hostname)

    @mock.patch.object(ippool, 'PodIP')
    def test_delete(self, pod_ip_mock):
        """Test IpAddrPool.delete method."""
        network = u'192.168.1.0/24'
        with self.assertRaises(APIError) as err:
            ippool.IpAddrPool().delete(network)
        self.assertEqual(err.exception.status_code, 404)

        pool = IPPool(network=network)
        db.session.add(pool)
        db.session.commit()

        pod_ip_mock.filter_by.return_value.first.return_value = 'aaa'
        with self.assertRaises(APIError):
            ippool.IpAddrPool().delete(network)
        pod_ip_mock.filter_by.assert_called_once_with(network=network)

        pod_ip_mock.filter_by.return_value.first.return_value = None
        ippool.IpAddrPool().delete(network)
        all_ = IPPool.query.all()
        self.assertEqual(all_, [])

    @responses.activate
    def test_create_sets_correctly_public_ip_counter(self):
        # Network contains 14 IPs
        # 192.168.2.1 - 192.168.2.14
        self._create_network(u'192.168.2.0/28')

        node = K8SNode(hostname=self.node.hostname)
        self.assertEqual(node.free_public_ip_count, 16)

    @responses.activate
    def test_create_sets_correctly_public_ip_counter_given_autoblock(self):
        # Network contains 14 IPs
        # 192.168.2.1 - 192.168.2.14
        # Autoblock leaves only 192.168.2.13, 192.168.2.14
        self._create_network(
            u'192.168.2.0/28', autoblock='192.168.2.1-192.168.2.12')

        node = K8SNode(hostname=self.node.hostname)
        self.assertEqual(node.free_public_ip_count, 4)

    @responses.activate
    def test_update_decreases_public_ip_counter_on_block_ip_request(self):
        # Network contains 14 IPs
        # 192.168.2.1 - 192.168.2.14
        network = u'192.168.2.0/28'
        self._create_network(network)

        params = {'block_ip': u'192.168.2.1', 'node': self.node.hostname}
        ippool.IpAddrPool().update(network, params)
        node = K8SNode(hostname=self.node.hostname)
        self.assertEqual(node.free_public_ip_count, 16 - 1)

    @responses.activate
    def test_update_increases_public_ip_counter_on_unblock_ip_request(self):
        # Network contains 14 IPs
        # 192.168.2.1 - 192.168.2.14
        network = u'192.168.2.0/28'
        self._create_network(network)

        update_params = [
            {'block_ip': u'192.168.2.1', 'node': self.node.hostname},
            {'unblock_ip': u'192.168.2.1', 'node': self.node.hostname}
        ]

        for p in update_params:
            ippool.IpAddrPool().update(network, p)

        node = K8SNode(hostname=self.node.hostname)
        self.assertEqual(node.free_public_ip_count, 16 - 1 + 1)

    @responses.activate
    def test_delete_correctly_decreases_public_ip_counter(self):
        # Networks contains 28 IPs
        networks = [u'192.168.2.0/28', u'192.168.3.0/28']
        for net in networks:
            self._create_network(net)
        ippool.IpAddrPool().delete(networks[0])
        node = K8SNode(hostname=self.node.hostname)
        self.assertEqual(node.free_public_ip_count, 16)

    @responses.activate
    def test_update_fails_on_ip_block_if_free_ip_counter_is_zero(self):
        # We have one ip in out network
        network = u'192.168.2.0/32'
        self._create_network(network)

        node = K8SNode(hostname=self.node.hostname)
        # Emulate situation when scheduler decreased counter in parallel
        node.update_free_public_ip_count(0)

        # Should fail as we try to block the only existing IP which was
        # reserved by pod not yet started but already scheduled by scheduler
        with self.assertRaises(APIError):
            ippool.IpAddrPool().update(network, {
                'block_ip': u'192.168.2.1',
                'node': self.node.hostname
            })

    def _create_network(self, network, autoblock=None):
        data = {
            'network': network,
            'autoblock': '' if autoblock is None else autoblock,
            'node': self.node.hostname,
        }
        ippool.IpAddrPool().create(data)


if __name__ == '__main__':
    unittest.main()
