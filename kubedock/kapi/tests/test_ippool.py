"""Unit tests for kapi.ippool
"""
import unittest

import mock
import ipaddress

from kubedock.core import db
from kubedock.kapi import ippool
from kubedock.pods.models import IPPool
from kubedock.testutils.testcases import DBTestCase
from kubedock.exceptions import APIError
from kubedock.testutils.testcases import attr


@attr('db')
class TestIpPool(DBTestCase):
    """Tests for ippool.IpAddrPool class"""

    def test_get(self):
        """Test IpAddrPool.get method."""
        res = ippool.IpAddrPool().get()
        self.assertEqual(res, [])

        res = ippool.IpAddrPool().get(net='somegarbage')
        self.assertIsNone(res)

        # add a pool
        pool = IPPool(network='somegarbage')
        db.session.add(pool)
        db.session.commit()
        with self.assertRaises(ValueError):
            ippool.IpAddrPool().get()
        db.session.query(IPPool).delete()
        db.session.commit()

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
            'page': 1,
            'pages': 1
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

    def test_get_free_host(self):
        """Test IpAddrPool.get_free method."""
        res = ippool.IpAddrPool().get_free()
        self.assertIsNone(res)

        pool = IPPool(network='192.168.1.0/24')
        db.session.add(pool)
        db.session.commit()
        res = ippool.IpAddrPool().get_free()
        self.assertEqual(res, '192.168.1.1')

    def test_create(self):
        """Test IpAddrPool.create method."""
        data = None
        with self.assertRaises(APIError):
            ippool.IpAddrPool().create(data)

        data = {}
        with self.assertRaises(APIError):
            ippool.IpAddrPool().create(data)

        data = {
            'network': u'192.168.1.1/32'
        }
        res = ippool.IpAddrPool().create(data)
        self.assertEqual(res, {'network': data['network'], 'autoblock': [],
                               'id': data['network'],
                               'allocation': [(u'192.168.1.1', None, 'free')]})

        expected_block_ips = [
            u'192.168.2.1', u'192.168.2.3', u'192.168.2.4',
            u'192.168.2.5', u'192.168.2.7'
        ]

        block = '1,3-5,7'

        data = {
            'network': u'192.168.2.0/24',
            'autoblock': block
        }
        res = ippool.IpAddrPool().create(data)
        self.assertEqual(
            {
                'network': res['network'],
                'autoblock': res['autoblock']
            },
            {
                'network': data['network'],
                'autoblock': [
                    int(ipaddress.ip_address(ip)) for ip in expected_block_ips
                ],
            }
        )

        invalid_block = 'qwerty'
        data = {
            'network': u'192.168.4.0/24',
            'autoblock': invalid_block
        }
        with self.assertRaises(APIError):
            res = ippool.IpAddrPool().create(data)

        networks = db.session.query(IPPool).order_by(IPPool.network)
        self.assertEqual(
            [item.network for item in networks],
            [u'192.168.1.1/32', u'192.168.2.0/24'],
        )

    @mock.patch.object(ippool.PodCollection, '_remove_public_ip')
    def test_update(self, remove_public_mock):
        """Test IpAddrPool.update method."""
        network = u'192.168.2.0/24'
        with self.assertRaises(APIError):
            ippool.IpAddrPool().update(network, None)

        pool = IPPool(network='192.168.1.0/24')
        db.session.add(pool)
        db.session.commit()

        block = '1,3-5,7'
        data = {
            'network': network,
            'autoblock': block
        }
        ippool.IpAddrPool().create(data)


        res1 = ippool.IpAddrPool().update(network, None)
        self.assertIsNotNone(res1)
        self.assertEqual(res1['network'], network)

        # add already blocked ip
        block_ip = u'192.168.2.1'
        params = {'block_ip': block_ip}
        res2 = ippool.IpAddrPool().update(network, params)
        self.assertEqual(res1, res2)

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
        all = IPPool.query.all()
        self.assertEqual(all, [])


if __name__ == '__main__':
    unittest.main()
