import unittest

from lib.integration_test_api import KDIntegrationTestAPI

# How to run integration tests
# activate kd_venv:                 $ workon kd
# create cluster and run tests:     $ BUILD_CLUSTER=1 nosetests -svv tests_integration
# run tests on existing cluster:    $ nosetests -svv tests_integration


class IntegrationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(IntegrationTests, cls).setUpClass()
        cls.cluster = KDIntegrationTestAPI()
        cls.cluster.start()

    @classmethod
    def tearDownClass(cls):
        super(IntegrationTests, cls).tearDownClass()
        cls.cluster.destroy()

    def setUp(self):
        super(IntegrationTests, self).setUp()
        self.cluster.cleanup()

    def tearDown(self):
        super(IntegrationTests, self).tearDown()
        pass

    def test_nginx(self):
        self.cluster.create_pod("nginx", "test_nginx_pod",
                                start=True,
                                wait_ports=True,
                                healthcheck=True)
