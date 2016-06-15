import unittest

from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import \
    NonZeroRetCodeException, pod_factory, NO_FREE_IPS_ERR_MSG


class TestNonFloatingIP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestNonFloatingIP, cls).setUpClass()

        env_vars = {
            'KD_NONFLOATING_PUBLIC_IPS': 'true',
            'KD_NODES_COUNT': '2',
            'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch'
        }
        cls.cluster = KDIntegrationTestAPI(override_envs=env_vars)

        try:
            cls.cluster.start()
            cls.cluster.preload_docker_image('nginx:latest')
        except:
            cls.cluster.destroy()
            raise

    @classmethod
    def tearDownClass(cls):
        super(TestNonFloatingIP, cls).tearDownClass()
        cls.cluster.destroy()

    def setUp(self):
        super(TestNonFloatingIP, self).setUp()
        self._cleanup()

        self.create_new_pods = pod_factory(self.cluster, 'nginx', start=True,
                                           wait_ports=False, healthcheck=False)

    def _cleanup(self):
        self.cluster.delete_all_pods()
        self.cluster.delete_all_ip_pools()

    def tearDown(self):
        super(TestNonFloatingIP, self).tearDown()

    def test_cannot_create_pod_with_public_ip_with_no_pools_in_cluster(self):
        with self.assertRaisesRegexp(
                NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
            self.create_new_pods()

        self.assertListEqual(self.cluster.get_all_pods(), [])

    def test_can_create_pod_without_public_ip_with_no_ip_pools(self):
        self.create_new_pods(1, open_all_ports=False,
                             wait_for_status='running')

    def test_can_not_add_pod_if_no_free_ips_available(self):
        expected_pod_count = 3
        # 2 IP addresses in a network
        self.cluster.add_ip_pool('192.168.0.0/30', 'node1')
        # 1 IP address in a network
        self.cluster.add_ip_pool('192.168.1.0/32', 'node2')

        pods = self.create_new_pods(
            expected_pod_count, wait_for_status='running')

        with self.assertRaisesRegexp(
                NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
            self.create_new_pods(1)

        # Make sure there are still expected_pod_count of pods
        self.assertTrue(len(self.cluster.get_all_pods()) == expected_pod_count)

        # Remove a pod to free an IP an try to add a new one - should succeed
        pods[0].delete()
        self.create_new_pods(1, wait_for_status='running')

        # It's not possible to create a pod once again
        with self.assertRaisesRegexp(
                NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
            self.create_new_pods(1)

        # But it's possible to create a pod without a public IP
        self.create_new_pods(open_all_ports=False, wait_for_status='running')

        # Make sure there are +1 pods
        pod_count = len(self.cluster.get_all_pods())
        self.assertTrue(pod_count == expected_pod_count + 1)

    def test_pods_are_not_created_on_node_without_free_ips(self):
        # 2 IP addresses in a network
        self.cluster.add_ip_pool('192.168.0.0/30', 'node1')

        self.create_new_pods(2, wait_for_status='running')

        node_names = (n['host'] for n in self.cluster.get_all_pods())
        self.assertTrue(all(n == 'node1' for n in node_names))
