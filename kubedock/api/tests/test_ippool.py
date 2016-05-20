import ipaddress
from kubedock.testutils.testcases import APITestCase
from kubedock.kapi.ippool import IpAddrPool, PodIP, IPPool


class TestIPPool(APITestCase):
    url = '/ippool'
    maxDiff = None

    def setUp(self):
        network = u'192.168.1.0/30'
        IpAddrPool().create({'network': network, 'autoblock': '1'})
        self.ippool = IPPool.query.get(network)
        self.pod = self.fixtures.pod(owner_id=self.user.id)
        self.pod_ip = PodIP(
            pod_id=self.pod.id,
            network=self.ippool.network,
            ip_address=int(ipaddress.ip_address(u'192.168.1.2')),
        )
        self.db.session.add(self.pod_ip)
        self.db.session.commit()

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

    def test_create(self):
        new_network = {'network': '192.168.2.0/30', 'autoblock': ''}
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
