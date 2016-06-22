import unittest

from lib.integration_test_api import KDIntegrationTestAPI

# How to run integration tests
# activate kd_venv:                 $ workon kd
# create cluster and run tests:     $ BUILD_CLUSTER=1 nosetests -svv tests_integration
# run tests on existing cluster:    $ nosetests -svv tests_integration
from tests_integration.lib.integration_test_utils import pod_factory, \
    NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG


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
