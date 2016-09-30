import unittest
from kubedock.kapi.helpers import Services
from kubedock.kapi.lbpoll import ExternalIPsService


class TestLoadBalancer(unittest.TestCase):


    def test_get_publicIP(self):
        conf = Services().get_template(
            'pod_id', [{"name":"port", "port": 80, "targetPort": 80}])
        publicIP = '10.0.0.1'
        self.assertEqual(None, ExternalIPsService().get_publicIP(conf))
        conf['spec']['externalIPs'] = [publicIP]
        self.assertEqual(publicIP, ExternalIPsService().get_publicIP(conf))
        self.assertEqual(
            {'pod_id': publicIP},
            ExternalIPsService().get_pods_publicIP({'pod_id': conf}))




