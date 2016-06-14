import json

import ipaddress
import responses

from kubedock.kapi.ippool import IpAddrPool, PodIP, IPPool
from kubedock.testutils.fixtures import K8SAPIStubs
from kubedock.testutils.testcases import APITestCase


class TestIPPool(APITestCase):
    url = '/ippool'
    maxDiff = None

    def setUp(self):
        network = u'192.168.1.0/30'
        self.node = self.fixtures.node()
        IpAddrPool().create(
            {'network': network, 'autoblock': '1', 'node': self.node.id})
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

    def test_get_user_ips(self):
        response = self.user_open(self.item_url('userstat'))
        self.assert200(response)
        self.assertEqual(response.json['data'], [{'id': '192.168.1.2',
                                                  'pod_id': self.pod.id,
                                                  'pod': self.pod.name}])

    def test_get(self):
        response = self.admin_open()
        self.assert200(response)  # TODO: check response format
        response = self.admin_open(self.item_url(self.ippool.network))
        self.assert200(response)  # TODO: check response format

    @responses.activate
    def test_create(self):
        new_network = {
            'network': '192.168.2.0/30', 'autoblock': '',
            'node': self.node.hostname
        }
        response = self.admin_open(method='POST', json=new_network)
        self.assert200(response)  # TODO: check response format

    def test_update(self):
        url = self.item_url(self.ippool.network)
        unblock = {'unblock_ip': '192.168.1.1'}
        response = self.admin_open(url, method='PUT', json=unblock)
        self.assert200(response)  # TODO: check response format
        response = self.admin_open(self.item_url(self.ippool.network))
        self.assert200(response)
        self.assertEqual(len(response.json['data']['blocked_list']), 0)

    def test_delete(self):
        url = self.item_url(self.ippool.network)
        self.assert400(self.admin_open(url, method='DELETE'))
        # free IPs before deletion
        self.db.session.delete(self.pod_ip)
        self.db.session.commit()
        self.assert200(self.admin_open(url, method='DELETE'))
