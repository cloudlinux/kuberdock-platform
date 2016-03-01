import logging
import mock
import sys
import unittest
import json
import copy
import ipaddress
from random import randrange, choice

from uuid import uuid4
from collections import namedtuple

from kubedock.testutils.testcases import DBTestCase, FlaskTestCase
from kubedock.testutils import create_app

from ..pod import Pod
from .. import podcollection, helpers
from ...utils import POD_STATUSES, APIError


global_patchers = [
    mock.patch.object(podcollection, 'current_app'),
    mock.patch.object(podcollection, 'license_valid'),
    mock.patch.object(helpers, 'current_app'),
]


def setUpModule():
    for patcher in global_patchers:
        patcher.start()


def tearDownModule():
    for patcher in global_patchers:
        patcher.stop()


def fake_pod(**kwargs):
    parents = kwargs.pop('use_parents', ())
    return type('Pod', parents,
                dict({
                    'namespace': 'n',
                    'owner': 'u',
                    'status': POD_STATUSES.running,
                }, **kwargs))()


class TestCase(FlaskTestCase):
    def create_app(self):
        return create_app(self)


class TestCaseMixin(object):
    def mock_methods(self, obj, *methods, **replace_methods):
        for method in methods:
            patcher = mock.patch.object(obj, method)
            self.addCleanup(patcher.stop)
            patcher.start()

        for method, replacement in replace_methods.iteritems():
            patcher = mock.patch.object(obj, method, replacement)
            self.addCleanup(patcher.stop)
            patcher.start()


# TODO: use DBTestCase
@mock.patch('kubedock.kapi.podcollection.DBPod', mock.Mock())
class TestPodCollectionDelete(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})

        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods',
                          '_merge', '_stop_pod', '_get', '_del', '_raise')

        self.app = podcollection.PodCollection(U())

    def test_pods_belonging_to_KUBERDOCK_INTERNAL_USER_are_not_deleted(self):
        """
        Tests that when pod owner is podcollection.KUBERDOCK_INTERNAL_USER an exception is raised
        """
        pod = fake_pod(sid='s', owner=podcollection.KUBERDOCK_INTERNAL_USER)

        pod.get_config = (lambda x: None)
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x, y: None)
        self.app._drop_namespace = (lambda x: None)

        self.app._raise.side_effect = Exception()

        try:
            # Making actual call
            self.app.delete(str(uuid4()))
        except Exception:
            pass

        self.assertTrue(self.app._raise.called)
        self.assertFalse(self.app._del.called)

    def test_pods_belonging_to_KUBERDOCK_INTERNAL_USER_deleted_if_forced(self):
        """
        Check if pod deletion actually takes place even if user is
        podcollection.KUBERDOCK_INTERNAL_USER when forced
        """
        pod = fake_pod(sid='s', owner=podcollection.KUBERDOCK_INTERNAL_USER)
        pod.get_config = (lambda x: None)

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x, y: None)
        self.app._drop_namespace = (lambda x: None)

        # Makiing actual call
        self.app.delete(str(uuid4()), force=True)

        # Checking our _del has been called only once with expected args
        self.app._stop_pod.assert_called_once_with(pod, raise_=False)
        self.assertFalse(self.app._raise.called)

    def test_delete_not_called_unless_sid_is_present(self):
        """
        Makes sure _del not called on sid-less pods (i.e pure kubernetes pods)
        """
        pod = fake_pod()
        pod.get_config = (lambda x: None)

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x, y: None)
        self.app._drop_namespace = (lambda x: None)

        # Making actual call
        self.app.delete(str(uuid4()))

        # Checking our _del has not been called
        self.assertFalse(self.app._del.called)

    @unittest.skip('Now all pods have Replication Controller')
    @mock.patch.object(podcollection.PodCollection, '_del')
    def test_delete_request_is_sent_for_serviceless_non_replica(self, del_):
        """
        If pod has no services and no replicas, only one delete request should be
        made (for deletion the pod itself)
        """
        pod = fake_pod(sid='s')
        pod.get_config = (lambda x: None)

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x,y: None)
        self.app._drop_namespace = (lambda x: None)

        # Makiing actual call
        self.app.delete(str(uuid4()))

        # Checking our _del has been called only once with expected args
        del_.assert_called_once_with(['k', 's'], ns='n')

    def test_delete_request_is_sent_for_serviceless_replica(self):
        """
        If serviceless pod has replicas (one replica for now) an attempt to stop
        cluster after pod deletion is expected to be made
        """
        pod = fake_pod(sid='s')
        pod.get_config = (lambda x: None)

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x, y: None)
        self.app._drop_namespace = (lambda x: None)

        # Making actual call
        self.app.delete(str(uuid4()))

        # Checking our _del has been called only once with expected args
        self.app._stop_pod.assert_called_once_with(pod, raise_=False)

    def test_delete_request_is_sent_twice_if_pod_has_service(self):
        """
        If a pod has a service then _del is expected to be called twice: for deletion
        a pod itself and for deletion its service. Moreover a _get request to learn
        about the service details is expected to be sent. Attempt to unbind IP address
        is not expected to be made
        """
        pod = fake_pod(sid='s')
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x, y: None)
        self.app._drop_namespace = (lambda x: None)

        self.app._get.return_value = {}  # we don't want to call modify_node_ips

        # Making actual call
        self.app.delete(str(uuid4()))

        # Checking our _get has been called only once with expected args
        #self.app._get.assert_called_once_with(['services', 'fs'], ns='n')

        # Making sure del_ has been called twice with proper params each time
        self.app._stop_pod.assert_called_once_with(pod, raise_=False)
        self.app._del.assert_called_once_with(['services', 'fs'], ns='n')

    @mock.patch.object(podcollection.PodCollection, '_remove_public_ip')
    @mock.patch('kubedock.kapi.podcollection.current_app')
    def test_pod_assigned_IPs_are_marked_as_free(self, ca_, free_):
        """
        Check if an attempt to free a pod public IP has been made after the deletion
        of the pod
        """
        # Real Pod instance
        pod = fake_pod(use_parents=(podcollection.ModelQuery,), sid='s', public_ip=True)
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x, y: None)
        self.app._drop_namespace = (lambda x: None)

        self.app._get.return_value = {
            'metadata': {},
            'spec': {
                'ports': []}}

        # Making actual call
        self.app.delete(str(uuid4()))

        self.assertTrue(free_.called, "pod._remove_public_ip is expected to be called")

    @mock.patch('kubedock.kapi.podcollection.current_app')
    @mock.patch.object(podcollection.PodCollection, '_drop_namespace')
    def test_namespace_is_dropped(self, dn_, ca_):
        """
        Check if an attempt to call _drop_namespace has been made.
        """
        pod = fake_pod(sid='s')
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._mark_pod_as_deleted = (lambda x: None)
        self.app._raise_if_failure = (lambda x, y: None)

        self.app._get.return_value = {
            'metadata': {},
            'spec': {
                'ports': []}}

        # Making actual call
        self.app.delete(str(uuid4()))

        dn_.assert_called_once_with('n')

    @mock.patch.object(podcollection.ModelQuery, '_mark_pod_as_deleted')
    @mock.patch('kubedock.kapi.podcollection.current_app')
    def test_pod_marked_as_deleted(self, ca_, mark_):
        """
        Check if an attempt to call _mark_pod_as_deleted has been made.
        """
        pod = fake_pod(sid='s')
        pod.get_config = (lambda x: 'fs')

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)
        self.app._raise_if_failure = (lambda x, y: None)
        self.app._drop_namespace = (lambda x: None)

        self.app._get.return_value = {
            'metadata': {},
            'spec': {
                'ports': []}}

        # Making actual call
        uuid = str(uuid4())
        self.app.delete(uuid)

        mark_.assert_called_once_with(uuid)


class TestPodCollectionRunService(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')
        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(podcollection.PodCollection, '_post')
    def test_pod_run_service(self, post_):
        """
        Test that _run_service generates expected service config
        :type post_: mock.Mock
        """
        # Fake Pod instance
        pod_name = 'bla bla pod'
        pod_id = str(uuid4())
        pod = fake_pod(use_parents=(Pod,), sid='s', name=pod_name, id=pod_id,
                       public_ip='127.0.0.1')

        pod.containers = [{
            'ports': [{'hostPort': 1000, 'containerPort': 80, 'isPublic': True},
                      {'containerPort': 80, 'isPublic': False}],
        }]

        # Making actual call
        self.pod_collection._run_service(pod)

        expected_service_conf = \
            '{"kind": "Service", "spec": {"sessionAffinity": "None", "type": ' \
            '"ClusterIP", "ports": [{"targetPort": 80, "protocol": "TCP", ' \
            '"name": "c0-p0", "port": 1000}, {"targetPort": 80, ' \
            '"protocol": "TCP", "name": "c0-p1", "port": 80}], "selector": ' \
            '{"kuberdock-pod-uid": "%(id)s"}}, "apiVersion": "v1", "metadata": ' \
            '{"generateName": "service-", "labels": {"name": ' \
            '"%(id)s-service"}}}' % {'id': pod_id}
        post_.assert_called_once_with(['services'], expected_service_conf,
                                      ns='n', rest=True)


class TestPodCollectionMakeNamespace(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})

        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')

        self.pod_collection = podcollection.PodCollection(U())
        self.test_ns = "user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094"

    @mock.patch.object(podcollection.PodCollection, '_post')
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

    @mock.patch.object(podcollection.PodCollection, '_post')
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


class TestPodCollectionGetNamespaces(TestCase, TestCaseMixin):

    def setUp(self):
        pods = [
            fake_pod(
                name='Unnamed-1',
                is_deleted=False,
                namespace='user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094'
            ),
            fake_pod(
                name='test-some-long.pod.name1',
                is_deleted=False,
                namespace='user-test-some-long-pod-name1-8e8843452313cdc9edec704dee6919bb'
            ),
            fake_pod(
                name='Pod with some weird name #3',
                is_deleted=False,
                namespace='ccc6736151b6011c2442c72ddb077be6'
            ),
        ]
        U = type('User', (), {'username': 'user', 'pods': pods})
        self.get_ns_patcher = mock.patch.object(podcollection.PodCollection, '_get_namespaces')
        self.addCleanup(self.get_ns_patcher.stop)
        self.get_ns_patcher.start()

        self.mock_methods(podcollection.PodCollection, '_get_pods', '_merge')

        self.pod_collection = podcollection.PodCollection(U())

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
            'ccc6736151b6011c2442c72ddb077be6',
        ]
        ns_items = {'items': [{'metadata': {'name': i}} for i in test_nses]}
        self.pod_collection._get = mock.Mock(return_value=ns_items)

        # Actual call
        self.pod_collection._get.reset_mock()
        self.get_ns_patcher.stop()
        res = self.pod_collection._get_namespaces()
        self.get_ns_patcher.start()

        self.pod_collection._get.assert_called_once_with(['namespaces'],
                                                         ns=False)
        self.assertEquals(res, test_nses[2:])

    @mock.patch.object(podcollection.PodCollection, '_del')
    def test_pod_drop_namespace(self, del_):
        """
        Test that _drop_namespace call _del with expected args.
        """
        test_ns = 'some-ns'

        # Actual call
        self.pod_collection._drop_namespace(test_ns)

        del_.assert_called_once_with(['namespaces', test_ns], ns=False)


class TestPodCollection(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        self.pods = [{'id': 1, 'name': 'Unnamed-1', 'namespace': 'Unnamed-1-namespace-md5',
                      'owner': 'user', 'containers': '', 'volumes': []},
                     {'id': 2, 'name': 'Unnamed-2', 'namespace': 'Unnamed-2-namespace-md5',
                      'owner': 'user', 'containers': '', 'volumes': []}]

        self.pods_output = copy.deepcopy(self.pods)
        for pod in self.pods_output:
            # Some fields excluded from output due to security
            pod.pop('namespace', None)

        U = type('User', (), {'username': 'user'})

        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')

        self.pod_collection = podcollection.PodCollection(U())
        self.pod_collection._collection = {}
        for data in self.pods:
            pod = Pod(data)
            self.pod_collection._collection[pod.name, pod.namespace] = pod

    def test_collection_get_as_json(self):
        self.assertEqual(json.loads(self.pod_collection.get()), self.pods_output)
        self.assertEqual(json.loads(self.pod_collection.get(1)), self.pods_output[0])

    def test_collection_get(self):
        self.assertListEqual(self.pod_collection.get(as_json=False), self.pods_output)
        self.assertEqual(self.pod_collection.get(1, as_json=False), self.pods_output[0])

    def test_collection_get_by_id_if_id_not_exist(self):
        with self.assertRaises(podcollection.PodNotFound):
            self.pod_collection.get(3)


class TestPodCollectionStartPod(TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'username': 'user'})

        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge', 'replace_config')

        self.pod_collection = podcollection.PodCollection(U())

        self.test_service_name = 'service-eu53y'
        self.pod_collection._run_service = mock.Mock(
            return_value={'metadata': {'name': self.test_service_name}})

        self.valid_config = '{"valid": "config"}'
        self.test_pod = fake_pod(
            use_parents=(mock.Mock,),
            name='unnamed-1',
            is_deleted=False,
            status=POD_STATUSES.stopped,
            kind='replicationcontrollers',
            namespace="user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094",
            containers=[{
                'ports': [{'hostPort': 1000, 'containerPort': 80,
                           'isPublic': True},
                          {'containerPort': 80, 'isPublic': False}],
                'name': '2dbgdc',
                'state': POD_STATUSES.stopped,
            }]
        )

    def _check_status(self, response, status):
        self.assertEqual(self.test_pod.status, status)
        self.assertEqual(self.test_pod.containers[0]['state'], status)
        self.assertEqual(response, self.test_pod.as_dict.return_value)

    @mock.patch.object(podcollection.PodCollection, '_raise_if_failure')
    @mock.patch.object(podcollection.PodCollection, '_post')
    @mock.patch.object(podcollection.PodCollection, '_make_namespace')
    def test_pod_normal_first_start(self, mk_ns, post_, rif):
        """
        Test first _start_pod in usual case
        :type post_: mock.Mock
        :type mk_ns: mock.Mock
        :type rif: mock.Mock
        """

        self.test_pod.get_config = mock.Mock(return_value={'volumes': []})
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        self.pod_collection._run_service.reset_mock()

        # Actual call
        res = self.pod_collection._start_pod(self.test_pod)

        mk_ns.assert_called_once_with(self.test_pod.namespace)
        self.test_pod.get_config.assert_called_once_with()
        self.pod_collection._run_service.assert_called_once_with(self.test_pod)
        self.test_pod.prepare.assert_called_once_with()
        post_.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self.assertEqual(rif.called, True)
        self._check_status(res, POD_STATUSES.pending)

    @mock.patch.object(podcollection.PodCollection, '_post')
    @mock.patch.object(podcollection.PodCollection, '_make_namespace')
    def test_pod_first_start_without_ports(self, mk_ns, post_):
        """
        Test first _start_pod for pod without ports
        :type post_: mock.Mock
        """
        saved_ports = self.test_pod.containers[0]['ports']
        self.test_pod.containers[0]['ports'] = []

        self.test_pod.get_config = mock.Mock(return_value={'volumes': []})
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        self.pod_collection._run_service.reset_mock()

        # Actual call
        res = self.pod_collection._start_pod(self.test_pod)

        mk_ns.assert_called_once_with(self.test_pod.namespace)
        self.test_pod.get_config.assert_called_once_with()
        self.assertEquals(self.pod_collection._run_service.called, False)
        self.test_pod.prepare.assert_called_once_with()
        post_.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self._check_status(res, POD_STATUSES.pending)

        self.test_pod.containers[0]['ports'] = saved_ports

    @mock.patch.object(podcollection.PodCollection, '_post')
    @mock.patch.object(podcollection.PodCollection, '_make_namespace')
    def test_pod_normal_second_start(self, mk_ns, post_):
        """
        Test second _start_pod in usual case
        :type post_: mock.Mock
        """

        self.test_pod.get_config = mock.Mock(
            return_value={'volumes': [], 'service': self.test_service_name})
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        self.pod_collection._run_service.reset_mock()

        # Actual call
        res = self.pod_collection._start_pod(self.test_pod)

        mk_ns.assert_called_once_with(self.test_pod.namespace)
        self.test_pod.get_config.assert_called_once_with()
        self.assertEquals(self.pod_collection._run_service.called, False)
        self.test_pod.prepare.assert_called_once_with()
        post_.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self._check_status(res, POD_STATUSES.pending)

    def test_needs_public_ip(self):
        test_conf = {
            'containers': [{
                'ports': [{'hostPort': 1000, 'containerPort': 80,
                           'isPublic': True},
                          {'containerPort': 80, 'isPublic': False}],
            }]
        }
        test_conf2 = {
            'containers': [{
                'ports': [{'hostPort': 1000, 'containerPort': 80,
                           'isPublic': False},
                          {'containerPort': 80, 'isPublic': False}],
            }]
        }
        self.assertTrue(self.pod_collection.needs_public_ip(test_conf))
        self.assertFalse(self.pod_collection.needs_public_ip(test_conf2))


class TestPodCollectionStopPod(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'username': 'user'})
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')
        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(podcollection.PersistentDisk, 'free')
    @mock.patch.object(podcollection.PodCollection, '_get')
    @mock.patch.object(podcollection.PodCollection, '_put')
    @mock.patch.object(podcollection.PodCollection, '_del')
    @mock.patch.object(podcollection.PodCollection, '_stop_cluster')
    @mock.patch.object(podcollection.PodCollection, '_raise_if_failure')
    def test_pod_normal_stop(self, rif, stop_cluster, del_, put_, get_, free_pd_mock):
        """
        Test _stop_pod in usual case
        :type del_: mock.Mock
        :type stop_cluster: mock.Mock
        :type rif: mock.Mock
        """
        pod = fake_pod(
            use_parents=(mock.Mock,),
            status=POD_STATUSES.running,
            namespace="user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094",
            containers=[{
                'name': '2dbgdc',
                'state': POD_STATUSES.running,
            }]
        )
        get_.return_value = {'spec': {}}

        # Actual call
        res = self.pod_collection._stop_pod(pod)

        self.assertEquals(pod.status, POD_STATUSES.stopped)
        get_.assert_called_once_with(['replicationcontrollers', pod.sid],
                                     ns=pod.namespace)
        put_.assert_called_once_with(['replicationcontrollers', pod.sid],
                                     json.dumps({'spec': {'replicas': 0}}),
                                     ns=pod.namespace, rest=True)
        del_.assert_called_once_with(['replicationcontrollers', pod.sid],
                                     ns=pod.namespace)
        stop_cluster.assert_called_once_with(pod)
        self.assertEquals(rif.called, True)

        free_pd_mock.assert_called_once_with(pod.id)

        self.assertEqual(pod.status, POD_STATUSES.stopped)
        self.assertEqual(pod.containers[0]['state'], POD_STATUSES.stopped)
        self.assertEqual(res, pod.as_dict.return_value)

    # TODO: "Pod is already stopped" test


@mock.patch.object(Pod, 'create')
class TestPodCollectionAdd(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge', '_save_pod', '_check_trial',
                          '_make_namespace')

        U = type(
            'User', (),
            {'id': 123, 'username': 'user', 'is_trial': lambda s: True}
        )

        self.pod = type('Pod', (), {
            'compose_persistent': mock.Mock(),
            '_forge_dockers': mock.Mock(),
            'as_dict': mock.Mock(),
            'namespace': 'n'
        })

        self.user = U()
        self.name = 'nginx'
        self.params = {'name': self.name, 'containers': ()}
        self.namespace = 'n'
        self.pod_collection = podcollection.PodCollection(self.user)

    @mock.patch.object(podcollection.PodCollection, '_make_secret', mock.Mock())
    @mock.patch.object(podcollection.Image, 'check_images_availability')
    def test_check_images_availability_called(self, check_, create_):
        images = ['wncm/test_image:4', 'quay.io/wncm/test_image']
        secrets = [('test_user', 'test_password', mock.ANY),
                   ('test_user2', 'test_password2', 'https://quay.io')]
        params = dict(self.params, containers=[
            {'image': images[0], 'secret': {'username': secrets[0][0],
                                            'password': secrets[0][1]}},
            {'image': images[1], 'secret': {'username': secrets[1][0],
                                            'password': secrets[1][1]}},
        ])
        self.pod_collection.add(params)
        check_.assert_called_once_with(images, secrets)

    @mock.patch.object(podcollection.PodCollection, '_make_namespace')
    def test_make_namespace_called(self, make_namespace_, create_):
        create_.return_value = self.pod()
        self.pod_collection.add(self.params)
        make_namespace_.assert_called_once_with(self.namespace)

    @mock.patch.object(podcollection.PodCollection, '_make_secret')
    def test_make_secret_called(self, make_secret_, create_):
        create_.return_value = self.pod()
        secrets = [('test_user', 'test_password', mock.ANY),
                   ('test_user2', 'test_password2', mock.ANY)]
        containers = [{
            'image': 'test/image',
            'secret': {'username': secrets[0][0], 'password': secrets[0][1]}
        }, {
            'image': 'quay.io/test/image',
            'secret': {'username': secrets[1][0], 'password': secrets[1][1]}
        }, {
            'image': 'test/no/secret'
        }]
        params = dict(self.params, containers=containers)

        self.pod_collection.add(params, skip_check=True)
        make_secret_.assert_has_calls([mock.call(self.namespace, *secrets[0]),
                                       mock.call(self.namespace, *secrets[1])],
                                      any_order=True)

    def test_check_trial_called(self, create_):
        self.pod_collection.add(self.params)
        self.pod_collection._check_trial.assert_called_once_with(self.params)

    @mock.patch('kubedock.kapi.podcollection.uuid4')
    def test_pod_create_called(self, uuid4_, create_):
        uuid4_.return_value = self.namespace
        create_.return_value = self.pod()
        self.pod_collection.add(self.params)
        create_.assert_called_once_with({
            'id': uuid4_.return_value,
            'name': self.name,
            'namespace': self.namespace,
            'containers': (),
            'owner': self.user
        })

    def test_pod_compose_persistent_called(self, create_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        pod_.compose_persistent.assert_called_once_with(self.user)

    def test_save_pod_called(self, create_):
        self.pod_collection.add(self.params)
        self.assertTrue(self.pod_collection._save_pod.called)

    def test_pod_forge_dockers_called(self, create_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        self.assertTrue(pod_._forge_dockers.called)

    @mock.patch.object(podcollection.PodCollection, 'needs_public_ip')
    def test_pod_needs_public_ip_called(self, _npip, create_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        self.assertTrue(_npip.called)

    def test_pod_as_dict_called(self, create_):
        pod_ = self.pod()
        create_.return_value = pod_
        self.pod_collection.add(self.params)
        self.assertTrue(pod_.as_dict.called)


class TestPodCollectionUpdate(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge',
                          '_start_pod', '_stop_pod', '_resize_replicas',
                          # '_do_container_action'
                          )

        U = type('User', (), {'username': 'oergjh'})
        self.pod_collection = podcollection.PodCollection(U())

    def _create_dummy_pod(self):
        """ Generate random pod_id and new mock pod. """
        return str(uuid4()), mock.create_autospec(Pod, instance=True)

    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    def test_pod_not_found(self, get_by_id_mock):
        """ if the pod was not found, update must raise an error """
        get_by_id_mock.side_effect = Exception
        pod_id, _ = self._create_dummy_pod()
        pod_data = {'command': 'start'}
        with self.assertRaises(Exception):
            self.pod_collection.update(pod_id, pod_data)
        get_by_id_mock.assert_called_once_with(pod_id)

    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    def test_pod_unknown_command(self, get_by_id_mock):
        """ In case of an unknown command, update must raise an error """
        pod_id, pod = self._create_dummy_pod()
        pod_data = {'command': 'some_weird_stuff'}
        get_by_id_mock.return_value = pod

        with self.assertRaises(Exception):
            self.pod_collection.update(pod_id, pod_data)
        get_by_id_mock.assert_called_once_with(pod_id)

    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    def test_pod_command(self, get_by_id_mock):
        """ Test usual cases (update with correct commands) """
        pod_id, pod = self._create_dummy_pod()
        get_by_id_mock.return_value = pod
        patch_method = lambda method: mock.patch.object(podcollection.PodCollection, method)

        with patch_method('_start_pod') as start_pod_mock:
            pod_data = {'command': 'start'}
            self.pod_collection.update(pod_id, pod_data)
            start_pod_mock.assert_called_once_with(pod, {})

        with patch_method('_stop_pod') as stop_pod_mock:
            pod_data = {'command': 'stop'}
            self.pod_collection.update(pod_id, pod_data)
            stop_pod_mock.assert_called_once_with(pod, {})

        with patch_method('_resize_replicas') as resize_replicas_mock:
            pod_data = {'command': 'resize'}
            resize_replicas_mock.return_value = 12345  # new length
            result = self.pod_collection.update(pod_id, pod_data)
            self.assertEqual(result, resize_replicas_mock.return_value)
            resize_replicas_mock.assert_called_once_with(pod, {})

        with patch_method('_change_pod_config') as change_pod_config_mock:
            pod_data = {'command': 'change_config'}
            self.pod_collection.update(pod_id, pod_data)
            change_pod_config_mock.assert_called_once_with(pod, {})

        # with patch_method('_do_container_action') as do_container_action_mock:
        #     pod_data = {'command': 'container_start'}
        #     self.pod_collection.update(pod_id, pod_data)
        #     do_container_action_mock.assert_called_with('start', pod_data)

        #     pod_data = {'command': 'container_stop'}
        #     self.pod_collection.update(pod_id, pod_data)
        #     do_container_action_mock.assert_called_with('stop', pod_data)

        #     pod_data = {'command': 'container_delete'}
        #     self.pod_collection.update(pod_id, pod_data)
        #     do_container_action_mock.assert_called_with('rm', pod_data)

        get_by_id_mock.assert_has_calls([mock.call(pod_id)] * 4)


@unittest.skip('Not supported')
class TestPodCollectionDoContainerAction(unittest.TestCase, TestCaseMixin):
    # some available actions
    actions = ('start', 'stop', 'rm')

    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')

        U = type('User', (), {'username': '4u5hfee'})
        self.pod_collection = podcollection.PodCollection(U())

    def _create_request(self):
        return choice(self.actions), {
            'nodeName': str(uuid4()),
            'containers': ','.join(str(uuid4()) for i in range(randrange(1, 10))),
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


class TestPodCollectionGetPods(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(
            podcollection.PodCollection, '_get_namespaces', '_merge',
            __init__=lambda self, owner=None: setattr(self, 'owner', owner)
        )

        U = type('User', (), {'username': '4u5hfee'})
        self.user = U()

    @staticmethod
    def _get_uniq_fake_pod(*args):
        pod = mock.MagicMock()
        pod.sid = str(uuid4())
        pod.id = str(uuid4())
        pod.name = str(uuid4())
        pod.namespace = str(uuid4())
        return pod

    @mock.patch.object(podcollection.PodCollection, '_get')
    def test_many_namespace_provided(self, get_mock):
        """
        Test that _get_pods generates right api calls
        in the case of multiple namespaces
        """
        get_mock.return_value = {'items': []}
        namespaces = [str(uuid4()) for i in range(randrange(2, 10))]

        pod_collection = podcollection.PodCollection(self.user)
        pod_collection._get_pods(namespaces)

        get_mock.assert_has_calls([
            mock.call([api], ns=namespace)
            for namespace in namespaces
            for api in ('pods', 'services', 'replicationcontrollers')
        ])

    @mock.patch('kubedock.kapi.podcollection.Pod')
    @mock.patch.object(podcollection.PodCollection, '_get')
    def test_replication(self, get_mock, PodMock):
        """
        If replication controller manages more then one pod,
        _get_pods should save only one of them in _collection
        """
        namespace = str(uuid4())
        get_mock.side_effect = lambda res, ns=None: {  # fake kubernates API
            'pods': {'items': [{'metadata': {'labels': {'name': name}}}
                               for name in ('pod1', 'pod1', 'pod1', 'pod2', 'pod2')]},
            'services': {'items': []},
            'replicationcontrollers': {'items': [
                {'spec': {'selector': {'name': 'pod1'}, 'replicas': 1},
                 'metadata': {'name': 'pod1'}},
                {'spec': {'selector': {'name': 'pod2'}, 'replicas': 1},
                 'metadata': {'name': 'pod2'}}
            ]}
        }[res[0]]

        def _get_uniq_fake_pod(item):
            pod = self._get_uniq_fake_pod()
            pod.id = item['metadata']['labels']['name']
            pod.name = pod.id + 'creepy invalid stuff !@#$'
            pod.namespace = namespace
            return pod
        PodMock.populate.side_effect = _get_uniq_fake_pod

        pod_collection = podcollection.PodCollection(self.user)
        pod_collection._get_pods([namespace])

        self.assertItemsEqual(pod_collection._collection.iterkeys(),
                              [('pod1', namespace), ('pod2', namespace)])

    @mock.patch('kubedock.kapi.podcollection.Pod')
    @mock.patch.object(podcollection.PodCollection, '_get')
    def test_services(self, get_mock, PodMock):
        """ _get_pods should take pod IP from the service this pod belong. """
        namespace = str(uuid4())
        ip_dispatcher = {'api': '1.1.1.1', 'db': '2.2.2.2'}
        get_mock.side_effect = lambda res, ns=None: {  # fake kubernates API
            'pods': {'items': [{'metadata': {'labels': {'app': app}}}
                               for app in ('api', 'api', 'api', 'db', 'db')]},
            'services': {'items': [
                {'spec': {'selector': {'app': 'api'},
                          'clusterIP': ip_dispatcher['api']}},
                {'spec': {'selector': {'app': 'db'},
                          'clusterIP': ip_dispatcher['db']}},
            ]},
            'replicationcontrollers': {'items': []}
        }[res[0]]

        generated_pods = set()

        def _get_uniq_fake_pod(item):
            pod = self._get_uniq_fake_pod()
            pod._app = item['metadata']['labels']['app']
            pod.namespace = namespace
            generated_pods.add(pod)
            return pod
        PodMock.populate.side_effect = _get_uniq_fake_pod

        pod_collection = podcollection.PodCollection(self.user)
        pod_collection._get_pods([namespace])

        for pod in pod_collection._collection.itervalues():
            self.assertEqual(pod.podIP, ip_dispatcher[pod._app])
            self.assertIn(pod, generated_pods)
            generated_pods.remove(pod)

    @mock.patch('kubedock.kapi.podcollection.Pod')
    @mock.patch.object(podcollection.PodCollection, '_get')
    def test_pods_metadata(self, get_mock, PodMock):
        """
        Pods in the resulting collection must be populated with metadata,
        using Pod.populate(<api-pod-item>)
        """
        namespace = str(uuid4())
        api_pod_items = [{'metadata': {'name': str(uuid4()), 'labels': {}}}
                         for i in range(5)]
        get_mock.side_effect = lambda res, ns=None: {  # fake kubernates API
            'pods': {'items': api_pod_items},
            'services': {'items': []},
            'replicationcontrollers': {'items': []}
        }[res[0]]
        PodMock.populate.side_effect = self._get_uniq_fake_pod

        pod_collection = podcollection.PodCollection(self.user)
        pod_collection._get_pods(namespace)

        PodMock.populate.assert_has_calls(map(mock.call, api_pod_items))


class TestPodCollectionIsRelated(unittest.TestCase, TestCaseMixin):
    def test_related(self):
        """
        Object is related iff all key/value pairs in selector exist in labels
        """
        labels = {str(uuid4()): str(uuid4()) for i in range(randrange(1, 10))}
        selector = {str(uuid4()): str(uuid4()) for i in range(randrange(1, 10))}

        self.assertFalse(podcollection.PodCollection._is_related(labels, selector))

        labels_related = labels.copy()
        # If all key/value pairs in selector exist in labels, then object is related
        labels_related.update(selector)
        self.assertTrue(podcollection.PodCollection._is_related(labels_related, selector))

        # empty selector will match any object
        self.assertTrue(podcollection.PodCollection._is_related(labels, {}))

        # if labels or selector is None, object is not related
        self.assertFalse(podcollection.PodCollection._is_related(labels, None))
        self.assertFalse(podcollection.PodCollection._is_related(None, selector))
        self.assertFalse(podcollection.PodCollection._is_related(None, None))


class TestPodCollectionStopCluster(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_merge', '_get_pods')
        U = type('User', (), {'username': '4u5hfee'})
        self.user = U()
        self.PodMock = namedtuple('Pod', ('id', 'name', 'namespace'))

    @mock.patch.object(podcollection.PodCollection, '_del')
    @mock.patch.object(podcollection.PodCollection, '_get')
    def test_delete_right_pods(self, get_mock, del_mock):
        """ _merge will fetch pods from db """
        pod_id, pod_name, namespace = str(uuid4()), 'test-app-pod', str(uuid4())
        pod = self.PodMock(pod_id, pod_name, namespace)
        pod_collection = podcollection.PodCollection(self.user)

        pod_collection._get.return_value = {'items': [
            {'metadata': {'name': 'pod1', 'labels': {'kuberdock-pod-uid': pod_id}}},
            {'metadata': {'name': 'pod2', 'labels': {'kuberdock-pod-uid': pod_id}}},
            {'metadata': {'name': 'pod3', 'labels': {'kuberdock-pod-uid': pod_id}}},
            {'metadata': {'name': 'pod4', 'labels': {'kuberdock-pod-uid': 'other-pod'}}},
            {'metadata': {'name': 'pod5', 'labels': {'kuberdock-pod-uid': 'other-pod2'}}},
        ]}

        pod_collection._stop_cluster(pod)

        get_mock.assert_called_once_with(['pods'], ns=namespace)
        del_mock.assert_has_calls([mock.call(['pods', 'pod1'], ns=namespace),
                                   mock.call(['pods', 'pod2'], ns=namespace),
                                   mock.call(['pods', 'pod3'], ns=namespace)])


class TestPodCollectionMerge(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        self.mock_methods(
            podcollection.PodCollection, '_get_namespaces', '_get_pods',
            __init__=lambda self, owner=None: setattr(self, 'owner', owner)
        )

        U = type('User', (), {'username': '4u5hfee'})
        self.user = U()

    @staticmethod
    def _get_uniq_fake_pod(data):
        pod = mock.create_autospec(Pod, instance=True)
        pod.__dict__.update(data)
        pod.__dict__.setdefault('sid', str(uuid4()))
        pod.__dict__.setdefault('name', str(uuid4()))
        pod.__dict__.setdefault('namespace', str(uuid4()))
        return pod

    def _get_fake_pod_model_instances(self, pods_total=10, namespaces_total=3):
        namespaces = [str(uuid4()) for i in range(namespaces_total)]
        pod_ids = [str(uuid4()) for i in range(pods_total)]
        pods_in_db = [{'id': pod_id,
                       'name': 'pod{0}'.format(i),
                       'namespace': namespaces[i % namespaces_total],
                       'owner': self.user,
                       'config': json.dumps({'name': pod_id,
                                             'kube_type': randrange(3),
                                             'containers': ()})}
                      for i, pod_id in enumerate(pod_ids)]
        pod_model_instances = []
        for i, data in enumerate(pods_in_db):
            pod_model_instance = mock.MagicMock()
            pod_model_instance.__dict__.update(data)
            pod_model_instance.__dict__.update(json.loads(data['config']))
            pod_model_instance.id = i
            pod_model_instances.append(pod_model_instance)
        return pod_model_instances

    @mock.patch.object(podcollection.PodCollection, '_fetch_pods')
    def test_pods_fetched(self, fetch_pods_mock):
        """ _merge will fetch pods from db """
        fetch_pods_mock.return_value = []
        pod_collection = podcollection.PodCollection()
        pod_collection._collection = {}
        pod_collection._merge()
        fetch_pods_mock.assert_called_once_with(users=True)

    @mock.patch('kubedock.kapi.podcollection.Pod')
    @mock.patch.object(podcollection.PodCollection, '_fetch_pods')
    def test_pods_in_db_only(self, fetch_pods_mock, pod_mock):
        """ If pod exists in db only, then _forge_dockers and add in _collection """
        generated_pods = []

        def pod_init_mock(data):
            pod = mock.create_autospec(Pod, instance=True)
            pod.__dict__.update(data)
            # pod.name = data['name']
            pod.containers = []
            generated_pods.append(pod)
            return pod
        pod_mock.side_effect = pod_init_mock

        pod_model_instances = self._get_fake_pod_model_instances()
        fetch_pods_mock.return_value = pod_model_instances

        pod_collection = podcollection.PodCollection()
        pod_collection._collection = {}
        pod_collection._merge()

        self.assertItemsEqual(
            zip(*pod_mock.call_args_list)[0],  # [(args, kwargs),..] > [args, args,..]
            [(json.loads(pod.config),) for pod in pod_model_instances]
        )
        for pod in generated_pods:
            pod._forge_dockers.assert_called_once_with()

        self.assertItemsEqual(
            pod_collection._collection.iterkeys(),
            ((pod.id, pod.namespace) for pod in pod_model_instances)
        )

    @mock.patch.object(podcollection.PodCollection, 'merge_lists')
    @mock.patch.object(podcollection.PodCollection, '_fetch_pods')
    def test_pods_in_db_and_kubernetes(self, fetch_pods_mock, merge_lists_mock):
        """ If pod exists in db and kubernetes, then merge """
        merge_lists_mock.return_value = tuple()

        pods_total = 10
        pod_model_instances = self._get_fake_pod_model_instances(pods_total)
        fetch_pods_mock.return_value = pod_model_instances  # retrieved from db

        pods_in_kubernetes = {  # retrieved from kubernates api
            (pod.id, pod.namespace): self._get_uniq_fake_pod({
                'id': pod.id,
                'sid': pod.name,
                'name': pod.name,
                'namespace': pod.namespace,
                'containers': []
            })
            for pod in pod_model_instances
        }

        pod_collection = podcollection.PodCollection()
        pod_collection._collection = pods_in_kubernetes.copy()
        pod_collection._merge()

        self.assertEqual(len(pod_collection._collection), pods_total)
        for pod in pod_model_instances:  # check that data from db was copied in pod
            pod_in_collection = pod_collection._collection[pod.id, pod.namespace]
            self.assertEqual(pod.id, pod_in_collection.id)
            self.assertEqual(pod.kube_type, pod_in_collection.kube_type)
        # check that containers lists were merged using "name" as key
        merge_lists_mock.assert_has_calls([
            mock.call([], [], 'name')
            for i in range(pods_total)
        ])


@mock.patch('kubedock.kapi.podcollection.TRIAL_KUBES', 10)
class TestPodCollectionCheckTrial(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_merge', '_get_pods')
        U = type('User', (), {'username': '4u5hfee'})
        self.user = U()

    @mock.patch.object(podcollection.PodCollection, '_raise')
    def test_enough_kubes(self, raise_mock):
        """ user is trial and have enough kubes for a new pod """
        self.user.is_trial = lambda: True
        self.user.kubes = 5
        pod = {'containers': [{'kubes': 2}, {'kubes': 2}, {'kubes': 1}]}
        podcollection.PodCollection(self.user)._check_trial(pod)
        self.assertFalse(raise_mock.called)

    @mock.patch.object(podcollection.PodCollection, '_raise')
    def test_not_enough_kubes(self, raise_mock):
        """ user is trial and don't have enough kubes for a new pod """
        self.user.is_trial = lambda: True
        self.user.kubes = 5
        pod = {'containers': [{'kubes': 2}, {'kubes': 4}]}
        podcollection.PodCollection(self.user)._check_trial(pod)
        raise_mock.assert_called_once_with(mock.ANY)

    @mock.patch.object(podcollection.PodCollection, '_raise')
    def test_user_is_not_trial(self, raise_mock):
        self.user.is_trial = lambda: False
        self.user.kubes = 5
        pod = {'containers': [{'kubes': 2}, {'kubes': 4}]}
        podcollection.PodCollection(self.user)._check_trial(pod)
        self.assertFalse(raise_mock.called)


class TestPodCollectionGetSecrets(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')

        U = type('User', (), {'username': 'oergjh'})
        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(podcollection.PodCollection, '_get')
    def test_get_secrets(self, get_mock):
        """Get secrets from kubernetes"""
        pod = fake_pod(id=str(uuid4()), secrets=('secret-1', 'secret-2'),
                       namespace=str(uuid4()))
        get_mock.return_value = {'kind': 'Secret', 'data': {
            '.dockercfg': ('eyJxdWF5LmlvIjogeyJhdXRoIjogImRYTmxjbTVoYldVeE9uQmh'
                           'jM04zYjNKa01RPT0iLCAiZW1haWwiOiAiYUBhLmEiIH19')
        }}
        username, password, registry = 'username1', 'password1', 'quay.io'

        secrets = self.pod_collection._get_secrets(pod)

        get_mock.assert_has_calls([
            mock.call(['secrets', 'secret-1'], ns=pod.namespace),
            mock.call(['secrets', 'secret-2'], ns=pod.namespace),
        ])
        self.assertEqual(secrets, [(username, password, registry)] * 2)

    @mock.patch.object(podcollection.PodCollection, '_get')
    def test_secret_not_found(self, get_mock):
        """
        If secret was not found in kubernetes, podcollection.PodCollection._get_secrets must
        raise an APIError
        """
        pod = fake_pod(id=str(uuid4()), secrets=('secret-1', 'secret-2'),
                       namespace=str(uuid4()))
        get_mock.return_value = {'kind': 'Status', 'message': 'smth\'s wrong'}

        with self.assertRaises(APIError):
            self.pod_collection._get_secrets(pod)


@mock.patch.object(podcollection.PodCollection, '_get_by_id')
class TestPodCollectionCheckUpdates(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')

        U = type('User', (), {'username': 'oergjh'})
        self.pod_collection = podcollection.PodCollection(U())

    def test_pod_not_found(self, get_by_id_mock):
        """If pod was not found, check_updates must raise an APIError"""
        get_by_id_mock.side_effect = Exception
        pod_id = str(uuid4())
        container_id = 'dfghji765redcvbhut'
        with self.assertRaises(Exception):
            self.pod_collection.check_updates(pod_id, container_id)
        get_by_id_mock.assert_called_once_with(pod_id)

    def test_container_not_found(self, get_by_id_mock):
        """
        If container with this id was not found in the pod,
        check_updates must raise an APIError
        """
        pod = fake_pod(id=str(uuid4()), containers=[
            {'image': 'nginx', 'imageID': 'ceab6053', 'name': 'oduhrg94'}
        ])
        get_by_id_mock.return_value = pod

        with self.assertRaises(APIError):
            self.pod_collection.check_updates(pod.id, 'wrong_id')

    @mock.patch.object(podcollection.PodCollection, '_get_secrets')
    @mock.patch.object(podcollection.Image, 'get_id', autospec=True)
    def test_with_secrets(self, get_image_id_mock, get_secrets_mock, get_by_id_mock):
        """Request secrets from kubernetes, format and pass to get_id"""
        Image = podcollection.Image
        image, image_id, container_id = 'nginx', 'ceab60537ad2d', 'oduhrg94her4'
        pod = fake_pod(id=str(uuid4()), secrets=('secret-1', 'secret-2'), containers=[
            {'image': image, 'imageID': image_id, 'name': container_id}
        ])
        secrets_full = (('user1', 'password', 'regist.ry'),
                        ('user2', 'p-0', 'quay.io'))

        get_by_id_mock.return_value = pod
        get_secrets_mock.return_value = secrets_full
        get_image_id_mock.return_value = image_id

        self.pod_collection.check_updates(pod.id, container_id)

        get_secrets_mock.assert_called_once_with(pod)
        get_image_id_mock.assert_called_once_with(Image(image), secrets_full)

    @mock.patch.object(podcollection.Image, 'get_id', autospec=True)
    def test_check_updates(self, get_image_id_mock, get_by_id_mock):
        """
        check_updates must return True if image_id in registry != imageID in pod spec.
        otherwise (if ids are equal) - return False.
        Raise APIError if it couldn't get image_id from registry
        """
        Image = podcollection.Image
        image, image_id, container_id = 'nginx', 'ceab60537ad2d', 'oduhrg94her4'
        pod = fake_pod(id=str(uuid4()), secrets=(), containers=[
            {'image': image, 'imageID': image_id, 'name': container_id}
        ])
        get_by_id_mock.return_value = pod

        get_image_id_mock.return_value = None
        with self.assertRaises(APIError):
            self.pod_collection.check_updates(pod.id, container_id)
        get_image_id_mock.assert_called_once_with(Image(image), [])

        get_image_id_mock.reset_mock()
        get_image_id_mock.return_value = image_id
        self.assertFalse(self.pod_collection.check_updates(pod.id, container_id))
        get_image_id_mock.assert_called_once_with(Image(image), [])

        get_image_id_mock.reset_mock()
        get_image_id_mock.return_value = 'new_id'
        self.assertTrue(self.pod_collection.check_updates(pod.id, container_id))
        get_image_id_mock.assert_called_once_with(Image(image), [])


class TestPodCollectionUpdateContainer(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces', '_get_pods', '_merge')
        U = type('User', (), {'username': 'oergjh'})
        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    @mock.patch.object(podcollection.PodCollection, '_stop_pod')
    @mock.patch.object(podcollection.PodCollection, '_start_pod')
    def test_update_container(self, start_pod_mock, stop_pod_mock, get_by_id_mock):
        """update_container must restart pod"""
        pod_id, container_id = str(uuid4()), str(uuid4())
        pod = fake_pod(id=pod_id)
        get_by_id_mock.return_value = pod

        self.pod_collection.update_container(pod_id, container_id)
        get_by_id_mock.assert_called_once_with(pod_id)
        stop_pod_mock.assert_called_once_with(pod)
        start_pod_mock.assert_called_once_with(pod)


# TODO: AC-1662 unbind ip from nodes and delete service
class TestRemoveAndReturnIP(DBTestCase):
    def setUp(self):
        from kubedock.pods.models import PodIP, IPPool
        self.ip = ipaddress.ip_address(u'192.168.43.4')
        self.with_ip_conf = {
            'public_ip': unicode(self.ip),
            'containers': [
                {'ports': [{'isPublic': True}, {}, {'isPublic': False}]},
                {'ports': [{'isPublic': True}, {}, {'isPublic': False}]},
            ],
        }
        self.without_ip_conf = {
            'public_ip_before_freed': unicode(self.ip),
            'containers': [
                {'ports': [{'isPublic_before_freed': True},
                           {'isPublic_before_freed': None},
                           {'isPublic_before_freed': False}]},
                {'ports': [{'isPublic_before_freed': True},
                           {'isPublic_before_freed': None},
                           {'isPublic_before_freed': False}]},
            ],
        }
        self.pod = self.fixtures.pod(config=json.dumps(self.with_ip_conf))
        self.ippool = IPPool(network='192.168.43.0/29').save()
        self.podip = PodIP(pod_id=self.pod.id, network=self.ippool.network,
                           ip_address=int(self.ip)).save()

    def _check_returned(self):
        from kubedock.pods.models import PodIP
        self.assertIsNotNone(PodIP.query.filter_by(pod=self.pod))

    def _check_removed_and_retrun_back(self):
        self.db.session.expire_all()
        self.assertEqual(self.pod.get_dbconfig(), self.without_ip_conf)
        self.assertTrue(self.db.inspect(self.podip).deleted)
        podcollection.PodCollection._return_public_ip(pod_id=self.pod.id)
        self._check_returned()

    def test_remove_public_ip_by_pod_id(self):
        podcollection.PodCollection._remove_public_ip(pod_id=self.pod.id)
        self._check_removed_and_retrun_back()

    def test_remove_public_ip_by_ip(self):
        podcollection.PodCollection._remove_public_ip(ip=int(self.ip))
        self._check_removed_and_retrun_back()

    def test_remove_public_ip_by_both(self):
        podcollection.PodCollection._remove_public_ip(pod_id=self.pod.id, ip=int(self.ip))
        self._check_removed_and_retrun_back()

    def test_failed_to_retrun(self):
        podcollection.PodCollection._remove_public_ip(pod_id=self.pod.id, ip=int(self.ip))
        self.ippool.block_ip(self.ippool.hosts(as_int=True))
        with self.assertRaises(Exception):
            podcollection.PodCollection._return_public_ip(pod_id=self.pod.id)
        self.ippool.unblock_ip(self.ippool.hosts(as_int=True))
        self.db.session.flush()
        self._check_removed_and_retrun_back()


class TestPodComposePersistent(DBTestCase):
    @mock.patch('kubedock.kapi.pod.get_storage_class')
    def test_defaults(self, get_storage_class_mock):
        self.user, _ = self.fixtures.user_fixtures()
        self.db.session.add(podcollection.PersistentDisk(
            name='present-2', owner=self.user, size=2
        ))
        self.db.session.commit()

        volumes_in = [
            {'name': 'vol-1', 'localStorage': True},
            {'name': 'vol-2', 'persistentDisk': {'pdName': 'wncm', 'pdSize': 5}},
            {'name': 'vol-3', 'persistentDisk': {'pdName': 'default-1'}},
            {'name': 'vol-4', 'persistentDisk': {'pdName': 'present-2'}},
        ]
        volumes_public = [
            {'name': 'vol-1', 'localStorage': True},
            {'name': 'vol-2', 'persistentDisk': {'pdName': 'wncm', 'pdSize': 5}},
            {'name': 'vol-3', 'persistentDisk': {'pdName': 'default-1', 'pdSize': 1}},
            {'name': 'vol-4', 'persistentDisk': {'pdName': 'present-2', 'pdSize': 2}},
        ]
        pod = Pod({'id': str(uuid4()),
                   'volumes': volumes_in,
                   'containers': [{'name': 'nginx', 'image': 'nginx'}]})
        pod.compose_persistent(self.user)
        self.assertEqual(getattr(pod, 'volumes_public'), volumes_public)


class TestPodCollectionChangePodConfig(TestCase, TestCaseMixin):

    def setUp(self):
        self.mock_methods(podcollection.PodCollection,
                          '_get_namespaces', '_get_pods', '_merge')

        self.node = 'node1.kuberdock.local'
        self.pod_collection = podcollection.PodCollection()

        self.valid_config = {'valid': 'config'}

        self.test_pod = fake_pod(
            use_parents=(mock.Mock,),
            name='unnamed-1',
            kind='replicationcontrollers',
            namespace='ns',
            id='fake-id',
            sid='some-id',
        )

    @mock.patch.object(podcollection.PodCollection, '_raise_if_failure')
    @mock.patch.object(podcollection.PodCollection, 'replace_config')
    @mock.patch.object(podcollection.PodCollection, '_put')
    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    def test_pin_pod_to_node(self, get_by_id, put, rep_config, raise_fail):
        get_by_id.return_value = self.test_pod
        self.test_pod.get_config = mock.Mock(return_value={'node': None})
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        # Actual call
        self.pod_collection._change_pod_config(
            self.test_pod,
            {'node': self.node},
        )

        self.assertTrue(self.test_pod.get_config.called)
        rep_config.assert_called_once_with(self.test_pod, {'node': self.node})
        get_by_id.assert_called_once_with(self.test_pod.id)
        self.assertTrue(self.test_pod.prepare.called)
        put.assert_called_once_with(
            [self.test_pod.kind, self.test_pod.sid],
            json.dumps(self.valid_config),
            rest=True,
            ns=self.test_pod.namespace
        )
        self.assertTrue(raise_fail.called)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger('TestPodCollection.test_pod').setLevel(logging.DEBUG)
    unittest.main()
