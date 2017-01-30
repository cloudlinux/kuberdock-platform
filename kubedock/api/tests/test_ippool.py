
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

import ipaddress
import responses

from kubedock.kapi.ippool import IpAddrPool, PodIP, IPPool
from kubedock.testutils.fixtures import K8SAPIStubs
from kubedock.testutils.testcases import APITestCase


class BaseTestIPPool(APITestCase):
    url = '/ippool'
    maxDiff = None

    def setUp(self):
        network = u'192.168.1.0/30'
        self.node = self.fixtures.node()
        IpAddrPool().create(
            {'network': network, 'autoblock': '192.168.1.1', 'node':
                self.node.id})
        self.ippool = IPPool.query.get(network)
        self.pod = self.fixtures.pod(owner_id=self.user.id)
        self.pod_ip = PodIP(
            pod_id=self.pod.id,
            network=self.ippool.network,
            ip_address=int(ipaddress.ip_address(u'192.168.1.2')),
        )
        self.db.session.add(self.pod_ip)
        self.db.session.add(self.node)
        self.db.session.commit()

        self.stubs = K8SAPIStubs()
        self.stubs.node_info_in_k8s_api(self.node.hostname)
        self.stubs.node_info_update_in_k8s_api(self.node.hostname)


class TestIPPool(BaseTestIPPool):
    def test_get_user_ips(self):
        response = self.user_open(self.item_url('userstat'))
        self.assert200(response)
        self.assertEqual(response.json['data'], [{'id': '192.168.1.2',
                                                  'pod_id': self.pod.id,
                                                  'pod': self.pod.name}])

    def test_get(self):
        response = self.admin_open()
        self.assert200(response)
        self.assertEqual(response.json,

                         {'data': [
                             {'allocation': [['192.168.1.0', None, 'free'],
                                             ['192.168.1.1', None,
                                              'blocked'],
                                             ['192.168.1.2',
                                              self.pod.name, 'busy'],
                                             ['192.168.1.3', None,
                                              'free']],
                              'blocked_list': ['192.168.1.1'],
                              'free_hosts': ['192.168.1.0',
                                             '192.168.1.3'],
                              'id': '192.168.1.0/30',
                              'ipv6': False,
                              'network': '192.168.1.0/30',
                              'node': None,
                              'page': 1,
                              'pages': 1}],
                             'status': 'OK'}

                         )
        response = self.admin_open(self.item_url(self.ippool.network))
        self.assert200(response)  # TODO: check response format

    @responses.activate
    def test_create(self):
        new_network = {
            'network': '192.168.2.0/30', 'autoblock': '',
            'node': self.node.hostname
        }
        response = self.admin_open(method='POST', json=new_network)
        self.assert200(response)
        self.assertEqual(response.json,
                         {'data': {
                             'allocation': [['192.168.2.0', None, 'free'],
                                            ['192.168.2.1', None, 'free'],
                                            ['192.168.2.2', None, 'free'],
                                            ['192.168.2.3', None, 'free']],
                             'blocked_list': [],
                             'free_hosts': ['192.168.2.0',
                                            '192.168.2.1',
                                            '192.168.2.2',
                                            '192.168.2.3'],
                             'id': '192.168.2.0/30',
                             'ipv6': False,
                             'network': '192.168.2.0/30',
                             'node': self.node.hostname,
                             'page': 1,
                             'pages': 1},
                          'status': 'OK'}

                         )

    def test_update(self):
        url = self.item_url(self.ippool.network)
        unblock = {'unblock_ip': '192.168.1.1'}
        response = self.admin_open(url, method='PUT', json=unblock)
        self.assert200(response)
        self.assertEqual(response.json,
                         {'data': {
                             'allocation': [['192.168.1.0', None, 'free'],
                                            ['192.168.1.1', None,
                                             'free'],
                                            ['192.168.1.2',
                                             self.pod.name, 'busy'],
                                            ['192.168.1.3', None,
                                             'free']],
                             'blocked_list': [],
                             'free_hosts': ['192.168.1.0',
                                            '192.168.1.1',
                                            '192.168.1.3'],
                             'id': '192.168.1.0/30',
                             'ipv6': False,
                             'network': '192.168.1.0/30',
                             'node': None,
                             'page': 1,
                             'pages': 1},
                             'status': 'OK'}

                         )
        response = self.admin_open(self.item_url(self.ippool.network))
        self.assert200(response)
        self.assertEqual(response.json,
                         {'data': {
                             'allocation': [['192.168.1.0', None, 'free'],
                                            ['192.168.1.1', None, 'free'],
                                            ['192.168.1.2', self.pod.name,
                                             'busy'],
                                            ['192.168.1.3', None, 'free']],
                             'blocked_list': [],
                             'free_hosts': ['192.168.1.0', '192.168.1.1',
                                            '192.168.1.3'],
                             'id': '192.168.1.0/30',
                             'ipv6': False,
                             'network': '192.168.1.0/30',
                             'node': None,
                             'page': 1,
                             'pages': 1},
                             'status': 'OK'}
                         )

    def test_delete(self):
        url = self.item_url(self.ippool.network)
        response = self.admin_open(url, method='DELETE')
        self.assert400(response)
        self.assertEqual(response.json,
                         {
                             'data': "You cannot delete this network "
                                     "'192.168.1.0/30' while some of "
                                     "IP-addresses of this network are "
                                     "assigned to Pods",
                             'details': {},
                             'status': u'error',
                             'type': u'APIError'}

                         )
        # free IPs before deletion
        self.db.session.delete(self.pod_ip)
        self.db.session.commit()
        response = self.admin_open(url, method='DELETE')
        self.assert200(response)
        self.assertEqual(response.json, {'status': 'OK'})


class TestIPPool_v2(BaseTestIPPool):
    def open(self, url=None, method='GET', json=None, auth=None, headers=None,
             version=None, **kwargs):
        return super(TestIPPool_v2, self).open(url, method, json, auth,
                                               headers, 'v2', **kwargs)

    def test_get(self):
        response = self.admin_open()
        self.assert200(response)
        self.assertEqual(response.json, {'status': 'OK', 'data': [
            {'free_host_count': 2, 'network': '192.168.1.0/30',
             'node': None, 'id': '192.168.1.0/30', 'ipv6': False}]})
        response = self.admin_open(self.item_url(self.ippool.network))
        self.assert200(response)
        self.assertEqual(response.json,
                         {'status': 'OK',
                          'data': {'free_host_count': 2,
                                   'network': '192.168.1.0/30',
                                   'node': None,
                                   'id': '192.168.1.0/30',
                                   'ipv6': False,
                                   'blocks': [
                                       [3232235776, 3232235776, 'free'],
                                       [3232235777, 3232235777, 'blocked'],
                                       [3232235778, 3232235778, 'busy',
                                        self.pod.name],
                                       [3232235779, 3232235779, 'free']]
                                   }})

    @responses.activate
    def test_create(self):
        new_network = {
            'network': '192.168.2.0/30', 'autoblock': '',
            'node': self.node.hostname
        }
        response = self.admin_open(method='POST', json=new_network)
        self.assert200(response)
        self.assertEqual(response.json, {
            'data': {'blocks': [[3232236032, 3232236035, u'free']],
                     'free_host_count': 4,
                     'id': '192.168.2.0/30',
                     'ipv6': False,
                     'network': '192.168.2.0/30',
                     'node': self.node.hostname},
            'status': 'OK'})

    @responses.activate
    def test_create_with_autoblock(self):
        new_network = {
            'network': '192.168.33.0/24',
            'autoblock': '192.168.33.0-192.168.33.214,'
                         '192.168.33.218-192.168.33.255',
            'node': self.node.hostname
        }
        response = self.admin_open(method='POST', json=new_network)
        self.assert200(response)
        self.assertEqual(
            response.json,
            {"data": {
                "blocks": [[3232243968, 3232244182, "blocked"],
                           [3232244183, 3232244185, "free"],
                           [3232244186, 3232244223, "blocked"]],
                "free_host_count": 3, "id": "192.168.33.0/24",
                "ipv6": False, "network": "192.168.33.0/24",
                "node": self.node.hostname}, "status": "OK"}
        )

    @responses.activate
    def test_create_with_autoblock_overlaps(self):
        new_network = {
            'network': '192.168.33.0/32',
            'autoblock': '192.168.33.0-192.168.33.214,'
                         '192.168.33.218-192.168.33.255',
            'node': self.node.hostname
        }
        response = self.admin_open(method='POST', json=new_network)
        self.assert200(response)
        self.assertEqual(
            response.json,
            {"data": {
                "blocks": [[3232243968, 3232243968, "blocked"]],
                "free_host_count": 0, "id": "192.168.33.0/32",
                "ipv6": False, "network": "192.168.33.0/32",
                "node": self.node.hostname}, "status": "OK"}
        )

    def test_update(self):
        url = self.item_url(self.ippool.network)
        unblock = {'unblock_ip': '192.168.1.1'}
        response = self.admin_open(url, method='PUT', json=unblock)
        self.assert200(response)
        self.assertEqual(response.json,

                         {'data': {
                             'blocks': [[3232235776, 3232235777, 'free'],
                                        [3232235778, 3232235778, 'busy',
                                         self.pod.name],
                                        [3232235779, 3232235779, 'free']],
                             'free_host_count': 3,
                             'id': '192.168.1.0/30',
                             'ipv6': False,
                             'network': '192.168.1.0/30',
                             'node': None},
                             'status': 'OK'}

                         )

        response = self.admin_open(self.item_url(self.ippool.network))
        self.assert200(response)
        self.assertEqual(response.json,

                         {'data': {
                             'blocks': [[3232235776, 3232235777, 'free'],
                                        [3232235778, 3232235778, 'busy',
                                         self.pod.name],
                                        [3232235779, 3232235779, 'free']],
                             'free_host_count': 3,
                             'id': '192.168.1.0/30',
                             'ipv6': False,
                             'network': '192.168.1.0/30',
                             'node': None},
                             'status': 'OK'}

                         )
