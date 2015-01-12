import unittest
from ..kuberesolver import KubeResolver
from .. import create_frontend_app
import json
import os


class KubeResolverTest(unittest.TestCase):
    def setUp(self):
        self.app = KubeResolver()
    
    def tearDown(self):
        self.app = None
        
    def test_there_are_replicas_in_reply(self):
        """Here we forge REST request/response with predefined data, containing only one replicationController"""
        def fake_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_replicas.json')
            with open(path) as f:
                return json.load(f)
        self.app._get_replicas = fake_request
        replicas = self.app._parse_replicas()
        self.assertEquals(len(replicas), 1, "Replicas list should have one item")
        self.assertIn('replicaSelector', replicas[0], "Replica must point to a pod set with replicaSelector")
        self.assertTrue(type(replicas[0]['replicaSelector']) is dict, "replicaSelector must be dict")
        
    def test_when_no_pods_in_replica_there_must_be_two_pods_units(self):
        """
        Here we forge REST request/response with predefined data, containing two pods. When no
        replicas found these pods are independent from each other
        """
        def fake_pod_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_pods.json')
            with open(path) as f:
                return json.load(f)
        self.app._get_pods = fake_pod_request
        pods = self.app._parse_pods()
        self.assertEquals(len(pods), 2, "There must be two unit (replica of two pods)")
        
    def test_when_pods_in_replica_there_must_be_one_pods_unit(self):
        """
        Here we forge REST request/response with predefined data, containing two pods. These pods comprise
        one replica, so we start to name it 'a unit'. There must be one unit of two pods
        """
        def fake_pod_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_pods.json')
            with open(path) as f:
                return json.load(f)
        def fake_replica_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_replicas.json')
            with open(path) as f:
                return json.load(f)
        self.app._get_pods = fake_pod_request
        self.app._get_replicas = fake_replica_request
        self.app._replicas = self.app._parse_replicas()
        pods = self.app._parse_pods()
        self.assertEquals(len(pods), 1, "There must be only one unit (replica of two pods)")
        
    def test_a_unit_has_entrypoints(self):
        """
        Replicated pod (unit) can have entrypoint with ip, port and so on.
        """
        def fake_pod_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_pods.json')
            with open(path) as f:
                return json.load(f)
        def fake_replica_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_replicas.json')
            with open(path) as f:
                return json.load(f)
        def fake_service_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_services.json')
            with open(path) as f:
                return json.load(f)
        self.app._get_pods = fake_pod_request
        self.app._get_replicas = fake_replica_request
        self.app._get_services = fake_service_request
        self.app._replicas = self.app._parse_replicas()
        self.app._pods = self.app._parse_pods()
        self.app._parse_services()
        self.assertIn('portalIP', self.app._pods[0], "'portalIP' attribute expected")
        self.assertIn('port', self.app._pods[0], "'port' attribute expected")
        self.assertTrue(self.app._pods[0]['service'], "Service attribute expected to be True")

    def test_label_relationship(self):
        """
        We need to check relationship between replicationController, service and pod
        to learn whether pod is replicated and serviced. Here we test relationship checker
        """
        a = {'name': 'All is good'}
        b = {'name': 'All is good'}
        c = {'name': 'This is wrong'}
        d = {'status': 'All is good'}
        self.assertTrue(self.app._is_related(a, b))
        self.assertFalse(self.app._is_related(a, c))
        self.assertFalse(self.app._is_related(a, d))
        
    def test_units_against_db(self):
        def fake_db_query():
            path = os.path.join(os.path.dirname(__file__), 'pods_from_db.json')
            with open(path) as f:
                return json.load(f)
        def fake_pod_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_pods.json')
            with open(path) as f:
                return json.load(f)
        def fake_replica_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_replicas.json')
            with open(path) as f:
                return json.load(f)
        def fake_service_request():
            path = os.path.join(os.path.dirname(__file__), 'valid_services.json')
            with open(path) as f:
                return json.load(f)
        self.app._select_pods_from_db = fake_db_query
        self.app._get_pods = fake_pod_request
        self.app._get_replicas = fake_replica_request
        self.app._get_services = fake_service_request
        
        self.app._replicas = self.app._parse_replicas()
        self.app._pods = self.app._parse_pods()
        self.app._parse_services()
        self.app._merge_with_db()
        self.assertEqual(len(self.app._pods), 3, "Pods list is expected to contain 3 items")
        