import logging
import mock
import sys
import unittest
import json
import random

from uuid import uuid4
from collections import namedtuple

# We want to mock real modules which could be missing on test system
sys.modules['kubedock.core'] = mock.Mock()
sys.modules['bitmath'] = mock.Mock()
sys.modules['ipaddress'] = mock.Mock()
sys.modules['blinker'] = mock.Mock()
sys.modules['flask'] = mock.Mock()
sys.modules['requests'] = mock.Mock()
sys.modules['kubedock.api'] = mock.Mock()
sys.modules['kubedock.pods.models'] = mock.Mock()
sys.modules['kubedock.utils'] = mock.Mock()
sys.modules['kubedock.kapi.pstorage'] = mock.Mock()

from ..podcollection import PodCollection, ModelQuery, KUBERDOCK_INTERNAL_USER
from ..pod import Pod

get_ns_patcher = mock.patch.object(PodCollection, '_get_namespaces')


class TestPodCollectionDelete(unittest.TestCase):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})
        get_ns_patcher.start()
        self.addCleanup(get_ns_patcher.stop)
        PodCollection._get_pods = (lambda s, n: None)
        PodCollection._merge = (lambda s: None)
        self.app = PodCollection(U())

    @mock.patch.object(PodCollection, '_raise')
    @mock.patch.object(PodCollection, '_del')
    def test_pods_belonging_to_KUBERDOCK_INTERNAL_USER_are_not_deleted(self, del_, raise_):
        """
        Tests that when pod owner is KUBERDOCK_INTERNAL_USER an exception is raised
        """
        #log = logging.getLogger('TestPodCollection.test_pod')
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n',
                               'owner':KUBERDOCK_INTERNAL_USER,
                               'replicationController':False})()
        pod.get_config = (lambda x: None)
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        # Making actual call
        self.app.delete(str(uuid4()))

        #log.debug(self.app.get_by_id(uuid).owner)
        self.assertTrue(raise_.called)
        #if del_.called:
        #    self.fail('An exception is expected')

    @mock.patch.object(PodCollection, '_raise')
    @mock.patch.object(PodCollection, '_del')
    def test_pods_belonging_to_KUBERDOCK_INTERNAL_USER_deleted_if_forced(self, del_, raise_):
        """
        Check if pod deletion actually takes place even if user is
        KUBERDOCK_INTERNAL_USER when forced
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n',
                               'owner':KUBERDOCK_INTERNAL_USER,
                               'replicationController':False})()
        pod.get_config = (lambda x: None)

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        # Makiing actual call
        self.app.delete(str(uuid4()), force=True)

        # Checking our _del has been called only once with expected args
        del_.assert_called_once_with(['k', 's'], ns='n')
        self.assertFalse(raise_.called)

    @mock.patch.object(PodCollection, '_del')
    def test_delete_not_called_unless_sid_is_present(self, del_):
        """
        Makes sure _del not called on sid-less pods (i.e pure kubernetes pods)
        """
        # Fake Pod instance
        pod = type('Pod', (), {'kind':'k','namespace':'n','owner':'u',
                               'replicationController':False})()
        pod.get_config = (lambda x: None)

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        # Making actual call
        self.app.delete(str(uuid4()))

        # Checking our _del has not been called
        self.assertFalse(del_.called)

    @mock.patch.object(PodCollection, '_del')
    def test_delete_request_is_sent_for_serviceless_non_replica(self, del_):
        """
        If pod has no services and no replicas, only one delete request should be
        made (for deletion the pod itself)
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':False})()
        pod.get_config = (lambda x: None)

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        # Makiing actual call
        self.app.delete(str(uuid4()))

        # Checking our _del has been called only once with expected args
        del_.assert_called_once_with(['k', 's'], ns='n')

    @mock.patch.object(PodCollection, '_stop_cluster')
    @mock.patch.object(PodCollection, '_del')
    def test_delete_request_is_sent_for_serviceless_replica(self, del_, stop_):
        """
        If serviceless pod has replicas (one replica for now) an attempt to stop
        cluster after pod deletion is expected to be made
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':True})()
        pod.get_config = (lambda x: None)

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        # Making actual call
        self.app.delete(str(uuid4()))

        # Checking our _del has been called only once with expected args
        del_.assert_called_once_with(['k', 's'], ns='n')
        self.assertTrue(stop_.called)

    @mock.patch('kubedock.kapi.podcollection.modify_node_ips')
    @mock.patch.object(PodCollection, '_del')
    @mock.patch.object(PodCollection, '_get')
    def test_delete_request_is_sent_twice_if_pod_has_service(self, get_, del_, mod_):
        """
        If a pod has a service then _del is expected to be called twice: for deletion
        a pod itself and for deletion its service. Moreover a _get request to learn
        about the service details is expected to be sent. Attempt to unbind IP address
        is not expected to be made
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':False})()
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        get_.return_value = {}  # we don't want to call modify_node_ips

        # Making actual call
        self.app.delete(str(uuid4()))

        # Checking our _get has been called only once with expected args
        get_.assert_called_once_with(['services', 'fs'], ns='n')

        # Making sure del_ has been called twice with proper params each time
        expected = [mock.call(['k', 's'], ns='n'),
                    mock.call(['services', 'fs'], ns='n')]
        self.assertEqual(del_.call_args_list, expected,
                         "Arguments for deletion pod and service differ from expected ones")

        # Making sure modify_node_ips has not been called
        self.assertFalse(mod_.called, "modify_node_ips is not expected to be called"
                         " if no 'assigned-to' property")

    @mock.patch('kubedock.kapi.podcollection.current_app')
    @mock.patch('kubedock.kapi.podcollection.modify_node_ips')
    @mock.patch.object(PodCollection, '_del')
    @mock.patch.object(PodCollection, '_get')
    def test_pod_assigned_IPs_are_cleared(self, get_, del_, mod_, ca_):
        """
        Check if an attempt to unbind IP address has been made and was successful.
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':False})()
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        get_.return_value = {
            'metadata':{
                'annotations':{
                    'public-ip-state':'{"assigned-to":"host1","assigned-pod-ip":"ip1","assigned-public-ip":"ip2"}'}},
            'spec':{
                'ports':[]}}
        mod_.return_value = True

        # Making actual call
        self.app.delete(str(uuid4()))

        # Making sure modify_node_ips has been called once with expected args
        mod_.assert_called_once_with('fs', 'host1', 'del', 'ip1', 'ip2', [], ca_)

    @mock.patch('kubedock.kapi.podcollection.current_app')
    @mock.patch('kubedock.kapi.podcollection.modify_node_ips')
    @mock.patch.object(PodCollection, '_raise')
    @mock.patch.object(PodCollection, '_del')
    @mock.patch.object(PodCollection, '_get')
    def test_pod_exception_raised_when_modified_node_ips_returns_false(self, get_, del_, raise_, mod_, ca_):
        """
        Check if an attempt to unbind IP address has been made and failed.
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':False})()
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        get_.return_value = {
            'metadata':{
                'annotations':{
                    'public-ip-state':'{"assigned-to":"host1","assigned-pod-ip":"ip1","assigned-public-ip":"ip2"}'}},
            'spec':{
                'ports':[]}}
        mod_.return_value = False

        # Making actual call
        self.app.delete(str(uuid4()))

        self.assertTrue(raise_.called, "self._raise is expected to be called")

    @mock.patch.object(ModelQuery, '_free_ip')
    @mock.patch('kubedock.kapi.podcollection.current_app')
    @mock.patch('kubedock.kapi.podcollection.modify_node_ips')
    @mock.patch.object(PodCollection, '_del')
    @mock.patch.object(PodCollection, '_get')
    def test_pod_assigned_IPs_are_marked_as_free(self, get_, del_, mod_, ca_, free_):
        """
        Check if an attempt to free a pod public IP has been made after the deletion
        of the pod
        """
        # Real Pod instance

        pod = type('Pod', (ModelQuery,), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':False, 'public_ip': True})()
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        get_.return_value = {
            'metadata':{
                'annotations':{
                    'public-ip-state':'{"assigned-to":"host1","assigned-pod-ip":"ip1","assigned-public-ip":"ip2"}'}},
            'spec':{
                'ports':[]}}
        mod_.return_value = True

        # Making actual call
        self.app.delete(str(uuid4()))

        self.assertTrue(free_.called, "pod._free_ip is expected to be called")

    @mock.patch('kubedock.kapi.podcollection.current_app')
    @mock.patch('kubedock.kapi.podcollection.modify_node_ips')
    @mock.patch.object(PodCollection, '_drop_namespace')
    @mock.patch.object(PodCollection, '_del')
    @mock.patch.object(PodCollection, '_get')
    def test_namespace_is_dropped(self, get_, del_, dn_, mod_, ca_):
        """
        Check if an attempt to call _drop_namespace has been made.
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':False})()
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)

        get_.return_value = {
            'metadata':{
                'annotations':{
                    'public-ip-state':'{"assigned-to":"host1","assigned-pod-ip":"ip1","assigned-public-ip":"ip2"}'}},
            'spec':{
                'ports':[]}}
        mod_.return_value = True

        # Making actual call
        self.app.delete(str(uuid4()))

        dn_.assert_called_once_with('n')

    @mock.patch.object(ModelQuery, '_mark_pod_as_deleted')
    @mock.patch('kubedock.kapi.podcollection.current_app')
    @mock.patch('kubedock.kapi.podcollection.modify_node_ips')
    @mock.patch.object(PodCollection, '_del')
    @mock.patch.object(PodCollection, '_get')
    def test_pod_marked_as_deleted(self, get_, del_, mod_, ca_, mark_):
        """
        Check if an attempt to call _mark_pod_as_deleted has been made.
        """
        # Fake Pod instance
        pod = type('Pod', (), {'sid':'s','kind':'k','namespace':'n','owner':'u',
                               'replicationController':False})()
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched PodCollection methods
        self.app.get_by_id = (lambda x: pod)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        get_.return_value = {
            'metadata':{
                'annotations':{
                    'public-ip-state':'{"assigned-to":"host1","assigned-pod-ip":"ip1","assigned-public-ip":"ip2"}'}},
            'spec':{
                'ports':[]}}
        mod_.return_value = True

        # Making actual call
        uuid = str(uuid4())
        self.app.delete(uuid)

        mark_.assert_called_once_with(uuid)

    def tearDown(self):
        self.app = None


class TestPodCollectionRunService(unittest.TestCase):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})
        PodCollection._get_namespaces = (lambda s: None)
        PodCollection._get_pods = (lambda s, n: None)
        PodCollection._merge = (lambda s: None)
        self.pod_collection = PodCollection(U())

    def test_make_dash(self):
        """
        Test _make_dash() must return string no longer then 'limit' and spaces
        replaced with dashes
        """
        pod = type('FakePod', (Pod,), {
            'name': 'Some Very long pod name that is not compatible with dns -1'
        })()
        res = pod._make_dash(limit=54)
        self.assertLessEqual(len(res), 54)
        self.assertNotIn(' ', res)

    @mock.patch.object(PodCollection, '_post')
    def test_pod_run_service(self, post_):
        """
        Test that _run_service generates expected service config
        :type post_: mock.Mock
        """
        # Fake Pod instance
        pod_name = 'bla bla pod'
        pod = type('Pod', (Pod,), {
            'sid': 's',
            'kind': 'k',
            'namespace': 'n',
            'owner': 'u',
            'public_ip': '127.0.0.1',
            'replicationController': False,
            'name': pod_name
        })()

        pod.containers = [{
            'ports': [{'hostPort': 1000, 'containerPort': 80, 'isPublic': True},
                      {'containerPort': 80, 'isPublic': False}],
        }]

        # Making actual call
        self.pod_collection._run_service(pod)

        expected_service_conf = \
            '{"kind": "Service", "spec": {"sessionAffinity": "None", "type": ' \
            '"ClusterIP", "ports": [{"targetPort": 80, "protocol": "TCP", ' \
            '"name": "c0-p0-public", "port": 1000}, {"targetPort": 80, ' \
            '"protocol": "TCP", "name": "c0-p1", "port": 80}], "selector": ' \
            '{"name": "bla bla pod"}}, "apiVersion": "v1", "metadata": ' \
            '{"generateName": "service-", "labels": {"name": ' \
            '"bla-bla-pod-service"}, "annotations": {"public-ip-state": ' \
            '"{\\"assigned-public-ip\\": \\"127.0.0.1\\"}"}}}'
        post_.assert_called_once_with(['services'], expected_service_conf,
                                      ns='n', rest=True)

    def tearDown(self):
        self.pod_collection = None


class TestPodCollectionMakeNamespace(unittest.TestCase):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})
        get_ns_patcher.start()
        self.addCleanup(get_ns_patcher.stop)
        PodCollection._get_pods = (lambda s, n: None)
        PodCollection._merge = (lambda s: None)
        self.pod_collection = PodCollection(U())
        self.test_ns = "user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094"

    @mock.patch.object(PodCollection, '_post')
    def test_pod_make_namespace_is_presented(self, post_):
        """
        Test that _make_namespace do nothing when ns already exists
        :type post_: mock.Mock
        """
        self.pod_collection._get_namespace = mock.Mock(return_value=True)

        # Actual call
        self.pod_collection._make_namespace(self.test_ns)

        self.pod_collection._get_namespace.assert_called_once_with(self.test_ns)
        self.assertEquals(post_.called, False)

    @mock.patch.object(PodCollection, '_post')
    def test_pod_make_namespace_new_created(self, post_):
        """
        Test that _make_namespace create new ns
        :type post_: mock.Mock
        """
        self.pod_collection._get_namespace = mock.Mock(return_value=None)

        # Actual call
        self.pod_collection._make_namespace(self.test_ns)

        ns_conf = '{"kind": "Namespace", "apiVersion": "v1", ' \
                  '"metadata": {"name": ' \
                  '"%s"}}' % self.test_ns
        self.pod_collection._get_namespace.assert_called_once_with(self.test_ns)
        post_.assert_called_once_with(['namespaces'], ns_conf, rest=True,
                                      ns=False)

    def tearDown(self):
        self.pod_collection = None


class TestPodCollectionGetNamespaces(unittest.TestCase):

    def setUp(self):
        pod = namedtuple('pod_tuple', ['name', 'is_deleted'])
        pods = [
            pod(name='Unnamed-1', is_deleted=False),
            pod(name='test-some-long.pod.name1', is_deleted=False),
        ]
        U = type('User', (), {'username': 'user', 'pods': pods})
        get_ns_patcher.start()
        self.addCleanup(get_ns_patcher.stop)
        PodCollection._get_pods = (lambda s, n: None)
        PodCollection._merge = (lambda s: None)
        self.pod_collection = PodCollection(U())

    def test_pod_get_namespaces(self):
        """
        Test that _get_namespaces returns list of correct namespaces for this
        user
        """
        test_nses = [
            'default',
            'kuberdock-internal-kuberdock-d-80ca388842da44badab255d8dccfca5c',
            'user-test-some-long-pod-name1-8e8843452313cdc9edec704dee6919bb',
            'user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094',
        ]
        ns_items = {'items': [{'metadata': {'name': i}} for i in test_nses]}
        self.pod_collection._get = mock.Mock(return_value=ns_items)

        # Actual call
        self.pod_collection._get.reset_mock()
        get_ns_patcher.stop()
        res = self.pod_collection._get_namespaces()
        get_ns_patcher.start()

        self.pod_collection._get.assert_called_once_with(['namespaces'],
                                                         ns=False)
        self.assertEquals(res, test_nses[2:])

    @mock.patch.object(PodCollection, '_del')
    def test_pod_drop_namespace(self, del_):
        """
        Test that _drop_namespace call _del with expected args.
        """
        test_ns = 'some-ns'

        # Actual call
        self.pod_collection._drop_namespace(test_ns)

        del_.assert_called_once_with(['namespaces', test_ns], ns=False)

    def tearDown(self):
        self.pod_collection = None


class TestPodCollection(unittest.TestCase):

    def setUp(self):
        self.pods = [{'id': 1, 'name': 'Unnamed-1', 'namespace': 'Unnamed-1-namespace-md5',
                      'owner': 'user', 'containers': ''},
                     {'id': 2, 'name': 'Unnamed-2', 'namespace': 'Unnamed-2-namespace-md5',
                      'owner': 'user', 'containers': ''}]
        U = type('User', (), {'username': 'user'})
        get_ns_patcher.start()
        self.addCleanup(get_ns_patcher.stop)
        PodCollection._merge = (lambda s: None)
        self.pod_collection = PodCollection(U())
        for data in self.pods:
            pod = Pod(data)
            self.pod_collection._collection[pod.name, pod.namespace] = pod

    def test_collection_get_as_json(self):
        self.assertEqual(self.pod_collection.get(True), json.dumps(self.pods))

    def test_collection_get_as_list(self):
        self.assertListEqual(self.pod_collection.get(False), self.pods)

    def test_collection_get_by_id_if_id_exist(self):
        self.assertIsInstance(self.pod_collection.get_by_id(1), Pod)

    @mock.patch.object(PodCollection, '_raise')
    def test_collection_get_by_id_if_id_not_exist(self, raise_):
        self.pod_collection.get_by_id(3)
        self.assertTrue(raise_.called)

    def tearDown(self):
        self.app = None


class TestPodCollectionStartPod(unittest.TestCase):

    def setUp(self):
        U = type('User', (), {'username': 'user'})
        PodCollection._get_pods = (lambda s, n: None)
        PodCollection._merge = (lambda s: None)
        self.pod_collection = PodCollection(U())

        self.test_service_name = 'service-eu53y'
        self.pod_collection._run_service = mock.Mock(
            return_value={'metadata': {'name': self.test_service_name}})

        self.valid_config = '{"valid": "config"}'
        self.test_pod = mock.Mock()
        self.test_pod.name = 'unnamed-1'
        self.test_pod.is_deleted = False
        self.test_pod.kind = 'replicationcontrollers'
        self.test_pod.namespace = "user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094"
        self.test_pod.containers = [{
            'ports': [{'hostPort': 1000, 'containerPort': 80, 'isPublic': True},
                      {'containerPort': 80, 'isPublic': False}],
        }]

    @mock.patch.object(PodCollection, '_raise_if_failure')
    @mock.patch.object(PodCollection, '_post')
    @mock.patch.object(PodCollection, '_make_namespace')
    def test_pod_normal_first_start(self, mk_ns, post_, rif):
        """
        Test first _start_pod in usual case
        :type post_: mock.Mock
        :type mk_ns: mock.Mock
        :type rif: mock.Mock
        """

        self.test_pod.get_config = mock.Mock(return_value=None)
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        self.pod_collection._run_service.reset_mock()

        # Actual call
        res = self.pod_collection._start_pod(self.test_pod)

        mk_ns.assert_called_once_with(self.test_pod.namespace)
        self.test_pod.get_config.assert_called_once_with('service')
        self.pod_collection._run_service.assert_called_once_with(self.test_pod)
        self.test_pod.prepare.assert_called_once_with()
        post_.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self.assertEquals(rif.called, True)
        self.assertEquals(res, {'status': 'pending'})

    @mock.patch.object(PodCollection, '_post')
    @mock.patch.object(PodCollection, '_make_namespace')
    def test_pod_first_start_without_ports(self, mk_ns, post_):
        """
        Test first _start_pod for pod without ports
        :type post_: mock.Mock
        """
        saved_ports = self.test_pod.containers[0]['ports']
        self.test_pod.containers[0]['ports'] = []

        self.test_pod.get_config = mock.Mock(return_value=None)
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        self.pod_collection._run_service.reset_mock()

        # Actual call
        res = self.pod_collection._start_pod(self.test_pod)

        mk_ns.assert_called_once_with(self.test_pod.namespace)
        self.test_pod.get_config.assert_called_once_with('service')
        self.assertEquals(self.pod_collection._run_service.called, False)
        self.test_pod.prepare.assert_called_once_with()
        post_.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self.assertEquals(res, {'status': 'pending'})

        self.test_pod.containers[0]['ports'] = saved_ports

    @mock.patch.object(PodCollection, '_post')
    @mock.patch.object(PodCollection, '_make_namespace')
    def test_pod_normal_second_start(self, mk_ns, post_):
        """
        Test second _start_pod in usual case
        :type post_: mock.Mock
        """

        self.test_pod.get_config = mock.Mock(
            return_value=self.test_service_name)
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        self.pod_collection._run_service.reset_mock()

        # Actual call
        res = self.pod_collection._start_pod(self.test_pod)

        mk_ns.assert_called_once_with(self.test_pod.namespace)
        self.test_pod.get_config.assert_called_once_with('service')
        self.assertEquals(self.pod_collection._run_service.called, False)
        self.test_pod.prepare.assert_called_once_with()
        post_.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self.assertEquals(res, {'status': 'pending'})

    def tearDown(self):
        self.pod_collection = None


class TestPodCollectionStopPod(unittest.TestCase):

    def setUp(self):
        U = type('User', (), {'username': 'user'})
        PodCollection._get_pods = (lambda s, n: None)
        PodCollection._merge = (lambda s: None)
        self.pod_collection = PodCollection(U())

    @mock.patch.object(PodCollection, '_del')
    @mock.patch.object(PodCollection, '_stop_cluster')
    @mock.patch.object(PodCollection, '_raise_if_failure')
    def test_pod_normal_first_start(self, rif, stop_cluster, del_):
        """
        Test _stop_pod in usual case
        :type del_: mock.Mock
        :type stop_cluster: mock.Mock
        :type rif: mock.Mock
        """
        pod = type('TestPod', (), {
            'status': 'Running',
            'kind': 'RC',
            'namespace': 'some_ns',
            'replicationController': True,
            'sid': 'yyy',
        })

        # Actual call
        res = self.pod_collection._stop_pod(pod)

        self.assertEquals(pod.status, 'stopped')
        del_.assert_called_once_with([pod.kind, pod.sid], ns=pod.namespace)
        stop_cluster.assert_called_once_with(pod)
        self.assertEquals(rif.called, True)
        self.assertEquals(res, {'status': 'stopped'})

    def tearDown(self):
        self.pod_collection = None


class TestPodCollectionAdd(unittest.TestCase):

    def setUp(self):
        U = type('User', (), {'username': 'user', 'is_trial': lambda s: True})
        get_ns_patcher.start()
        self.addCleanup(get_ns_patcher.stop)
        PodCollection._get_pods = lambda s, n: None
        PodCollection._merge = lambda s: None
        self.pod = type('User', (), {
            'compose_persistent': mock.Mock(),
            '_forge_dockers': mock.Mock(),
            '_allocate_ip': mock.Mock(),
            'as_dict': mock.Mock()
        })
        self.user = U()
        self.name = 'nginx'
        self.params = {'name': self.name}
        self.namespace = 'n'
        self.pod_collection = PodCollection(self.user)

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_check_trial_called(self, check_trial_, create_, save_pod_):
        self.pod_collection.add(self.params)
        check_trial_.assert_called_once_with(self.params)

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch('kubedock.kapi.podcollection.generate_ns_name')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_pod_create_called(self, check_trial_, generate_, create_, save_pod_):
        generate_.return_value = self.namespace
        create_.return_value(self.pod)
        self.pod_collection.add(self.params)
        create_.assert_called_once_with({
            'name': self.name,
            'namespace': self.namespace,
            'owner': self.user
        })

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_pod_compose_persistent_called(self, check_trial_, create_, save_pod_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        pod_.compose_persistent.assert_called_once_with(self.user.username)

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_save_pod_called(self, check_trial_, create_, save_pod_):
        self.pod_collection.add(self.params)
        self.assertTrue(save_pod_.called)

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_pod_forge_dockers_called(self, check_trial_, create_, save_pod_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        self.assertTrue(pod_._forge_dockers.called)

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_pod_allocate_ip_not_called(self, check_trial_, create_, save_pod_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        self.assertFalse(pod_._allocate_ip.called)

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_pod_allocate_ip_called(self, check_trial_, create_, save_pod_):
        pod_ = self.pod()
        pod_.public_ip = True
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        self.assertTrue(pod_._allocate_ip.called)

    @mock.patch.object(PodCollection, '_save_pod')
    @mock.patch.object(Pod, 'create')
    @mock.patch.object(PodCollection, '_check_trial')
    def test_pod_as_dict_called(self, check_trial_, create_, save_pod_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        self.assertTrue(pod_.as_dict.called)

    def tearDown(self):
        self.pod = None
        self.user = None
        self.name = None
        self.params = None
        self.namespace = None
        self.pod_collection = None


class TestPodCollectionUpdate(unittest.TestCase):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        methods = ('_get_namespaces', '_get_pods', '_merge', '_start_pod',
                   '_stop_pod', '_resize_replicas', '_do_container_action')
        for method in methods:
            patcher = mock.patch.object(PodCollection, method)
            self.addCleanup(patcher.stop)
            patcher.start()

        U = type('User', (), {'username': 'oergjh'})
        self.pod_collection = PodCollection(U())

    def _create_dummy_pod(self):
        """ Generate random pod_id and new mock pod. """
        return str(uuid4()), mock.create_autospec(Pod, instance=True)

    @mock.patch.object(PodCollection, 'get_by_id')
    def test_pod_not_found(self, get_by_id_mock):
        """ if the pod was not found, update must raise an error """
        get_by_id_mock.side_effect = Exception
        pod_id, _ = self._create_dummy_pod()
        pod_data = {'command': 'start'}
        with self.assertRaises(Exception):
            self.pod_collection.update(pod_id, pod_data)
        get_by_id_mock.assert_called_once_with(pod_id)

    @mock.patch.object(PodCollection, 'get_by_id')
    def test_pod_unknown_command(self, get_by_id_mock):
        """ In case of an unknown command, update must raise an error """
        pod_id, pod = self._create_dummy_pod()
        pod_data = {'command': 'some_weird_stuff'}
        get_by_id_mock.return_value = pod

        with self.assertRaises(Exception):
            self.pod_collection.update(pod_id, pod_data)
        get_by_id_mock.assert_called_once_with(pod_id)

    @mock.patch.object(PodCollection, 'get_by_id')
    def test_pod_command(self, get_by_id_mock):
        """ Test usual cases (update with correct commands) """
        pod_id, pod = self._create_dummy_pod()
        get_by_id_mock.return_value = pod
        patch_method = lambda method: mock.patch.object(PodCollection, method)

        with patch_method('_start_pod') as start_pod_mock:
            pod_data = {'command': 'start'}
            self.pod_collection.update(pod_id, pod_data)
            start_pod_mock.assert_called_once_with(pod, pod_data)

        with patch_method('_stop_pod') as stop_pod_mock:
            pod_data = {'command': 'stop'}
            self.pod_collection.update(pod_id, pod_data)
            stop_pod_mock.assert_called_once_with(pod, pod_data)

        with patch_method('_resize_replicas') as resize_replicas_mock:
            pod_data = {'command': 'resize'}
            resize_replicas_mock.return_value = 12345  # new length
            result = self.pod_collection.update(pod_id, pod_data)
            self.assertEqual(result, resize_replicas_mock.return_value)
            resize_replicas_mock.assert_called_once_with(pod, pod_data)

        with patch_method('_do_container_action') as do_container_action_mock:
            pod_data = {'command': 'container_start'}
            self.pod_collection.update(pod_id, pod_data)
            do_container_action_mock.assert_called_with('start', pod_data)

            pod_data = {'command': 'container_stop'}
            self.pod_collection.update(pod_id, pod_data)
            do_container_action_mock.assert_called_with('stop', pod_data)

            pod_data = {'command': 'container_delete'}
            self.pod_collection.update(pod_id, pod_data)
            do_container_action_mock.assert_called_with('rm', pod_data)

        get_by_id_mock.assert_has_calls([mock.call(pod_id)] * 6)


class TestPodCollectionDoContainerAction(unittest.TestCase):
    # some available actions
    actions = ('start', 'stop', 'rm')

    def setUp(self):
        # mock all these methods to prevent any accidental calls
        for method in ('_get_namespaces', '_get_pods', '_merge'):
            patcher = mock.patch.object(PodCollection, method)
            self.addCleanup(patcher.stop)
            patcher.start()

        U = type('User', (), {'username': '4u5hfee'})
        self.pod_collection = PodCollection(U())

    def _create_request(self):
        return random.choice(self.actions), {
            'nodeName': str(uuid4()),
            'containers': ','.join(str(uuid4()) for i in range(random.randrange(1, 10))),
        }

    @mock.patch('kubedock.kapi.podcollection.run_ssh_command')
    @mock.patch('kubedock.kapi.podcollection.send_event')
    def test_no_host(self, send_event_mock, run_ssh_command_mock):
        """ If nodeName isn't specified, do nothing. """
        action, data = self._create_request()
        del data['nodeName']
        result = self.pod_collection._do_container_action(action, data)

        self.assertIsNone(result)
        self.assertFalse(send_event_mock.called)
        self.assertFalse(run_ssh_command_mock.called)

    @mock.patch('kubedock.kapi.podcollection.run_ssh_command')
    @mock.patch('kubedock.kapi.podcollection.send_event')
    def test_run_ssh_command_called(self, send_event_mock, run_ssh_command_mock):
        """ Check result. Check that `run_ssh_command` has right calls. """
        run_ssh_command_mock.return_value = status, message = 0, 'ok'

        action, data = self._create_request()
        result = self.pod_collection._do_container_action(action, data)

        self.assertDictEqual(
            result,
            {container: message for container in data['containers'].split(',')}
        )
        run_ssh_command_mock.assert_has_calls(
            [mock.call(data['nodeName'], mock.ANY) for _ in data['containers'].split(',')]
        )

    @mock.patch('kubedock.kapi.podcollection.run_ssh_command')
    @mock.patch('kubedock.kapi.podcollection.send_event')
    def test_send_event_called(self, send_event_mock, run_ssh_command_mock):
        """ When "start" or "stop" called, event "pull_pod_state" should be sent """
        run_ssh_command_mock.return_value = status, message = 0, 'ok'

        action, data = self._create_request()
        self.pod_collection._do_container_action('start', data)
        send_event_mock.assert_has_calls(
            [mock.call('pull_pod_state', message) for _ in data['containers'].split(',')]
        )
        action, data = self._create_request()
        self.pod_collection._do_container_action('stop', data)
        send_event_mock.assert_has_calls(
            [mock.call('pull_pod_state', message) for _ in data['containers'].split(',')]
        )

    @mock.patch('kubedock.kapi.podcollection.run_ssh_command')
    @mock.patch('kubedock.kapi.podcollection.send_event')
    def test_docker_error(self, send_event_mock, run_ssh_command_mock):
        """ Raise an error, if exit status of run_ssh_command is not equal 0 """
        run_ssh_command_mock.return_value = status, message = 1, 'sh-t happens'

        action, data = self._create_request()
        with self.assertRaises(Exception):
            self.pod_collection._do_container_action(action, data)
        run_ssh_command_mock.assert_called_once_with(data['nodeName'], mock.ANY)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger('TestPodCollection.test_pod').setLevel(logging.DEBUG)
    unittest.main()
