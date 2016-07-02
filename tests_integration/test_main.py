import unittest

from lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import pod_factory, \
    NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG


# TODO: to API add method, which creates IP pools via kdclt instead of manage.py
# then use this method to manage IP pools inside this class
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(IntegrationTests, cls).setUpClass()
        env_vars = {
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
        super(IntegrationTests, cls).tearDownClass()
        cls.cluster.destroy()

    def setUp(self):
        super(IntegrationTests, self).setUp()
        self._cleanup()

    def tearDown(self):
        super(IntegrationTests, self).tearDown()

    def _cleanup(self):
        self.cluster.delete_all_pods()
        self.cluster.forget_all_pods()
        self.cluster.delete_all_pvs()

    def test_nginx(self):
        # It is possible to create an nginx pod with public IP
        pod = self.cluster.create_pod("nginx", "test_nginx_pod_1",
                                      start=True, wait_ports=True,
                                      wait_for_status='running',
                                      healthcheck=True)
        pod.delete()

        # TODO: move to 'networking' pipeline when pipelines introduced
        # It's not possible to create a POD with public IP with no IP
        # pools
        self.cluster.delete_all_ip_pools()
        with self.assertRaisesRegexp(
                NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
            self.cluster.create_pod("nginx", "test_nginx_pod_2", start=True)

        self.assertListEqual(self.cluster.get_all_pods(), [])

        # Test if it's possible to create a pod without a public IP
        self.cluster.create_pod("nginx", "test_nginx_pod_3",
                                start=True, open_all_ports=False,
                                healthcheck=False, wait_ports=False,
                                wait_for_status='running')

    def test_cadvisor_errors(self):
        """Check cadvisor error/warning appears in uwsgi (AC-3499)"""

        self.cluster.kdctl('license show')

        # TODO: Remove once AC-3618 implemented
        cmd = "[ $(journalctl --since '15 min ago' -m -t uwsgi | " \
              "grep -v 'ssl_stapling' | " \
              "egrep 'warn|err' -c) -eq 0 ]"
        self.cluster.ssh_exec('master', cmd)

    def test_a_pv_created_together_with_pod(self):
        pv1_name = "disk107"
        mount_path = '/nginxpv'

        # It is possible to create an nginx pod together with new PV
        pv = self.cluster.create_pv("dummy", pv1_name, mount_path)
        pod = self.cluster.create_pod("nginx", "test_nginx_pod_1", pvs=[pv],
                                      start=True, wait_ports=True,
                                      wait_for_status='running',
                                      healthcheck=True)
        self.assertTrue(pv.exists())
        pod.delete()

        # It is possible to create an nginx pod using existing PV
        pod = self.cluster.create_pod("nginx", "test_nginx_pod_2", pvs=[pv],
                                      start=True, wait_ports=True,
                                      wait_for_status='running',
                                      healthcheck=True)
        pod.delete()

        # It's possible to remove PV created together with pod
        pv.delete()
        self.assertFalse(pv.exists())

    def test_a_pv_created_separately(self):
        pv2_name = "disk207"
        pv2_size = 2
        mount_path = '/nginxpv'

        # It is possible to create a separate PV
        pv = self.cluster.create_pv("new", pv2_name, mount_path, pv2_size)
        self.assertTrue(pv.exists())
        self.assertEqual(pv.size, pv2_size)

        # It's possible to use separately created PV for nginx pod
        pod = self.cluster.create_pod("nginx", "test_nginx_pod_3", pvs=[pv],
                                      start=True, wait_ports=False,
                                      wait_for_status='running',
                                      healthcheck=False)

        # TODO: place correct exception and regexp to args of assertRaisesRegexp
        # TODO: and uncomment the next block. Currently blocked by AC-3689
        '''
        # It's not possible to create pod using assigned PV
        with self.assertRaisesRegexp(some_exception, some_regexp):
            pod = self.cluster.create_pod("nginx", "test_nginx_pod_4",
                                          start=True, wait_ports=False,
                                          wait_for_status='running',
                                          healthcheck=False, pv_size=pv.size,
                                          pv_name=pv.name,
                                          pv_mount_path='/nginxpv')
        '''
