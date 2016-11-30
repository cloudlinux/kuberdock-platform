"""Unit tests for kapi.ippool
"""
import unittest

import mock
import responses

from kubedock.core import db
from kubedock.exceptions import APIError
from kubedock.kapi import ippool
from kubedock.pods.models import IPPool
from kubedock.testutils.fixtures import K8SAPIStubs
from kubedock.testutils.testcases import DBTestCase
from kubedock.kapi.node import Node as K8SNode
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

        current_app.config['FIXED_IP_POOLS'] = True

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
        current_app.config['FIXED_IP_POOLS'] = False
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
        pool = ippool.IpAddrPool().create(data)
        self.assertEqual(pool.network, data['network'])
        self.assertEqual(pool.node, self.node)
        self.assertEqual(pool.get_blocked_set(), set([]))
        self.assertEqual(pool.ipv6, False)
        self.assertEqual(pool.free_hosts(), ['192.168.1.1'])

    @responses.activate
    def test_create_correctly_excludes_blocks(self):
        pool = IPPool(network='192.168.1.1/32')
        db.session.add(pool)
        db.session.commit()

        expected_block_ips = {u'192.168.2.1', u'192.168.2.3', u'192.168.2.4',
                              u'192.168.2.5', u'192.168.2.7'}

        block = '192.168.2.1,192.168.2.3-192.168.2.5,192.168.2.7'

        data = {
            'network': u'192.168.2.0/24',
            'autoblock': block,
            'node': self.node.hostname,
        }
        pool = ippool.IpAddrPool().create(data)
        self.assertEqual({
            'network': pool.network,
            'blocked_list': pool.get_blocked_set()
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

        pool = ippool.IpAddrPool().update(network, None)
        self.assertIsNotNone(pool)
        blocked_list1 = pool.get_blocked_set()
        self.assertEqual(pool.network, network)

        # add already blocked ip
        block_ip = u'192.168.2.1'
        params = {'block_ip': block_ip}
        with self.assertRaises(APIError):
            ippool.IpAddrPool().update(network, params)

        # block new ip
        block_ip1 = u'192.168.2.111'
        params = {'block_ip': block_ip1}
        blocked_list = ippool.IpAddrPool().update(network, params)\
            .get_blocked_set()
        self.assertEqual(
            blocked_list,
            blocked_list1 | {block_ip1}
        )

        # and one else
        block_ip2 = u'192.168.2.112'
        params = {'block_ip': block_ip2}
        blocked_list = ippool.IpAddrPool().update(network, params)\
            .get_blocked_set()
        self.assertEqual(
            blocked_list,
            blocked_list1 | {block_ip1, block_ip2}
        )

        unblock_ip = block_ip1
        params = {'unblock_ip': unblock_ip}
        blocked_list = ippool.IpAddrPool().update(network, params)\
            .get_blocked_set()
        self.assertEqual(
            blocked_list,
            blocked_list1 | {block_ip2}
        )

        self.assertFalse(remove_public_mock.called)

        unbind_ip = '192.168.2.222'
        params = {'unbind_ip': unbind_ip}
        blocked_list = ippool.IpAddrPool().update(network, params)\
            .get_blocked_set()
        self.assertEqual(
            blocked_list,
            blocked_list1 | {block_ip2}
        )
        remove_public_mock.assert_called_once_with(ip=unbind_ip)

        pool = ippool.IpAddrPool().update(network, {'node': node.hostname})
        self.assertEqual(pool.node, node)

    @mock.patch.object(ippool.IpAddrPool, '_check_if_network_used_by_pod')
    def test_delete(self, network_check_mock):
        """Test IpAddrPool.delete method."""
        network = u'192.168.1.0/24'
        with self.assertRaises(APIError) as err:
            ippool.IpAddrPool().delete(network)
        self.assertEqual(err.exception.status_code, 404)

        pool = IPPool(network=network)
        db.session.add(pool)
        db.session.commit()

        network_check_mock.side_effect = APIError()
        with self.assertRaises(APIError):
            ippool.IpAddrPool().delete(network)

        network_check_mock.side_effect = None
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

    @responses.activate
    def test_is_ip_available(self):
        block = '["192.168.2.1","192.168.2.3","192.168.2.7"]'
        pool1 = IPPool(network='192.168.1.1/32')
        pool2 = IPPool(
            network='192.168.2.0/24', blocked_list=block, node=self.node)
        db.session.add(pool1)
        db.session.add(pool2)
        db.session.commit()

        self.assertTrue(pool1.is_ip_available(ip=u'192.168.1.1'))
        self.assertFalse(pool1.is_ip_available(ip=u'192.168.1.2'))
        self.assertFalse(pool1.is_ip_available(ip=u'192.168.2.2'))
        self.assertTrue(pool2.is_ip_available(ip='192.168.2.2'))
        self.assertFalse(pool2.is_ip_available(ip='192.168.2.7'))
        self.assertTrue(pool1.is_ip_available(
            ip=u'192.168.1.1', node_hostname=self.node.hostname))
        self.assertTrue(pool2.is_ip_available(
            ip=u'192.168.2.6', node_hostname=self.node.hostname))
        self.assertFalse(pool2.is_ip_available(
            ip=u'192.168.2.7', node_hostname=self.node.hostname))
        self.assertFalse(pool2.is_ip_available(
            ip=u'192.168.2.6', node_hostname="some_other_node"))

    @responses.activate
    def test_get_networks_list(self):
        network = u'192.168.2.0/32'
        self._create_network(network)

        res = ippool.IpAddrPool().get_networks_list()
        self.assertEqual(res,
                         [{'node': self.node.hostname,
                           'free_host_count': 1,
                           'ipv6': False,
                           'id': '192.168.2.0/32',
                           'network': '192.168.2.0/32'}]
                         )

    @mock.patch('kubedock.kapi.ippool.AWS', True)
    def test_get_networks_list_aws(self):
        res = ippool.IpAddrPool.get_networks_list()
        self.assertEqual(res, [
            {'node': None, 'free_host_count': 0, 'ipv6': False, 'id': None,
             'network': None}])

    @responses.activate
    def test_get_network_ips(self):
        network = u'192.168.2.0/32'
        self._create_network(network)

        res = ippool.IpAddrPool().get_network_ips(network)
        self.assertEqual(res,
                         {'node': self.node.hostname,
                          'free_host_count': 1,
                          'ipv6': False,
                          'id': '192.168.2.0/32',
                          'network': '192.168.2.0/32',
                          'blocks': [(3232236032, 3232236032, 'free')]}
                         )

    @responses.activate
    def test_get_network_ips_24(self):
        network = u'192.168.2.0/24'
        self._create_network(network)

        res = ippool.IpAddrPool().get_network_ips(network)
        self.assertEqual(res,
                         {'node': self.node.hostname,
                          'free_host_count': 256,
                          'ipv6': False,
                          'id': '192.168.2.0/24',
                          'network': '192.168.2.0/24',
                          'blocks': [(3232236032, 3232236287, 'free')]}
                         )

    @responses.activate
    @mock.patch('kubedock.kapi.ippool.AWS', True)
    @mock.patch.object(ippool, 'Pod')
    @mock.patch('kubedock.kapi.ippool.LoadBalanceService')
    def test_get_network_ips_aws(self, LoadBalanceService, Pod):
        mock_pod = mock.Mock()
        mock_pod.id = 'id'
        mock_pod.name = 'name'
        mock_pod.owner.username = 'owner'
        LoadBalanceService.return_value = mock.Mock(get_dns_by_pods=lambda
            x: {y: y for y in x})
        Pod.query.filter().all.return_value = [mock_pod]
        res = ippool.IpAddrPool().get_network_ips(None)
        self.assertEqual(res,
                         {'blocks': [('id', 'id', 'busy', 'name', 'owner')],
                          'free_host_count': 0,
                          'id': 'aws',
                          'ipv6': False,
                          'network': None,
                          'node': None}

                         )


if __name__ == '__main__':
    unittest.main()
