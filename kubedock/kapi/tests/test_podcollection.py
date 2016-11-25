import copy
import json
import logging
import sys
import unittest
from random import randrange, choice
from uuid import uuid4

import ipaddress
import mock
import responses
import re

from kubedock.testutils import create_app
from kubedock.testutils.testcases import DBTestCase, FlaskTestCase
from kubedock.kapi import helpers
from kubedock.kapi.lbpoll import PUBLIC_SVC_TYPE
from .. import pod_domains
from .. import pod as kapi_pod
from .. import podcollection
from ..images import Image
from ..pod import Pod
from ..podcollection import settings
from ...exceptions import APIError, NoSuitableNode
from ...rbac.models import Role
from ...users.models import User
from ...utils import POD_STATUSES, NODE_STATUSES
from ...pods.models import Pod as DBPod

global_patchers = [
    mock.patch.object(podcollection, 'licensing'),
]


def mock_k8s_ingress_endpoints():
    base_url = r'http://{}:{}/'.format(settings.KUBE_API_HOST, settings.KUBE_API_PORT)
    url_re = re.compile(
        base_url + 'apis/extensions/v1beta1/namespaces/.+/ingresses')

    responses.add(responses.GET, url_re, body='{"kind": "ingress"}', status=200,
                  content_type='application/json')

    url_re = re.compile(
        base_url + 'apis/extensions/v1beta1/namespaces/.+/ingresses/?.*')
    responses.add(responses.DELETE, url_re, status=200,
                  body='{"kind": "Status", "code": 200, "status": "Success"}',
                  content_type='application/json')


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
                    'id': str(uuid4()),
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


class TestPodCollectionDelete(DBTestCase, TestCaseMixin):
    def setUp(self):
        self.user, _ = self.fixtures.user_fixtures()
        self.internal_user = User.get(settings.KUBERDOCK_INTERNAL_USER)

        self.mock_methods(podcollection.PodCollection,
                          '_get_namespaces', '_get_pods',
                          '_merge', '_stop_pod')
        self.mock_methods(podcollection.KubeQuery,
                          'get', 'delete')

        self.app = podcollection.PodCollection(self.user)

    def test_pods_belonging_to_KUBERDOCK_INTERNAL_USER_are_not_deleted(self):
        """
        Tests that when pod owner is podcollection.KUBERDOCK_INTERNAL_USER
        an exception is raised
        """
        pod = fake_pod(sid='s', owner=self.internal_user)

        self.app._get_by_id = (lambda x: pod)

        with self.assertRaises(APIError):
            self.app.delete(str(uuid4()))

        self.assertFalse(self.app.k8squery.delete.called)

    @mock.patch.object(podcollection.dns_management, 'delete_record')
    @mock.patch.object(podcollection.helpers, 'mark_pod_as_deleted')
    @mock.patch.object(podcollection.podutils, 'raise_if_failure')
    @mock.patch.object(podcollection.PodCollection, '_drop_namespace')
    @mock.patch.object(podcollection.helpers, 'get_pod_config')
    @mock.patch.object(podcollection.PersistentDisk, 'free')
    def test_pods_belonging_to_KUBERDOCK_INTERNAL_USER_deleted_if_forced(
            self, mock_free_pd, get_pod_config, drop_namespace,
            raise_if_failure, mark_pod_as_deleted, delete_record_mock):
        """
        Check if pod deletion actually takes place even if user is
        podcollection.KUBERDOCK_INTERNAL_USER when forced
        """
        db_pod = self.fixtures.pod(owner=self.internal_user)
        pod = fake_pod(sid='s', owner=db_pod.owner, id=db_pod.id,
                       use_parents=(mock.Mock,),
                       domain='someuser-somepod.somehost.some')
        get_pod_config.return_value = None
        delete_record_mock.return_value = (True, None)

        # Monkey-patched podcollection.PodCollection methods
        self.app._get_by_id = (lambda x: pod)

        # Makiing actual call
        self.app.delete(pod.id, force=True)

        mock_free_pd.assert_called_once_with(pod.id)
        pod.set_status.assert_called_once_with(
            POD_STATUSES.deleting, send_update=True, force=True)
        drop_namespace.assert_called_once_with(pod.namespace, force=True)
        mark_pod_as_deleted.assert_called_once_with(pod.id)
        delete_record_mock.assert_called_once_with(pod.domain, 'A')

    @mock.patch.object(podcollection.PodCollection, '_drop_network_policies')
    @mock.patch.object(podcollection.dns_management, 'delete_record')
    @mock.patch.object(podcollection.PodCollection, '_drop_namespace')
    @mock.patch.object(podcollection.podutils, 'raise_if_failure')
    @mock.patch.object(podcollection.helpers, 'mark_pod_as_deleted')
    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    @mock.patch.object(podcollection.helpers, 'get_pod_config')
    @mock.patch.object(podcollection.PersistentDisk, 'free')
    def test_delete_not_called_unless_sid_is_present(
            self, mock_free_pd,
            get_pod_config,
            get_by_id,
            mark_pod_as_deleted,
            raise_if_failure,
            drop_namespace,
            delete_record_mock,
            drop_net_policy_mock):
        """
        Makes sure _del not called on sid-less pods (i.e pure kubernetes pods)
        """
        db_pod = self.fixtures.pod(owner=self.user)
        pod = fake_pod(owner=db_pod.owner, id=db_pod.id,
                       use_parents=(mock.Mock,),
                       domain='someuser-somepod.somehost.some')
        get_pod_config.return_value = None
        delete_record_mock.return_value = (True, None)

        # Monkey-patched podcollection.PodCollection methods
        get_by_id.return_value = pod

        # Making actual call
        self.app.delete(pod.id)

        # Checking our k8s delete query has not been called
        self.assertFalse(self.app.k8squery.delete.called)
        mock_free_pd.assert_called_once_with(pod.id)
        delete_record_mock.assert_called_once_with(pod.domain, 'A')

    @mock.patch.object(podcollection.dns_management, 'delete_record')
    @mock.patch.object(podcollection.PodCollection, '_drop_network_policies')
    @mock.patch.object(podcollection.PodCollection, '_remove_public_ip')
    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    @mock.patch.object(podcollection.PodCollection, '_drop_namespace')
    @mock.patch.object(podcollection.helpers, 'get_pod_config')
    @mock.patch.object(podcollection.PersistentDisk, 'free')
    @mock.patch.object(podcollection.helpers, 'mark_pod_as_deleted')
    @mock.patch.object(podcollection.podutils, 'raise_if_failure')
    def test_pod_delete(self, ca_, mark_, mock_free_pd,
                        get_pod_config_mock, pc_drop_namespace_mock,
                        pc_get_by_id_mock,
                        remove_ip_mock,
                        _drop_network_policies,
                        delete_record_mock,
                        *args, **kwargs):
        """
        Check if an attempt to call mark_pod_as_deleted has been made.
        """
        db_pod = self.fixtures.pod(owner=self.user)
        pod = fake_pod(sid='s', owner=db_pod.owner, id=db_pod.id,
                       public_ip=True, use_parents=(mock.Mock,),
                       domain='someuser-somepod.somehost.some')
        delete_record_mock.return_value = (True, None)
        get_pod_config_mock.return_value = 'fs'

        # Monkey-patched podcollection.PodCollection methods
        pc_get_by_id_mock.return_value = pod

        self.app.k8squery.get.return_value = {
            'metadata': {},
            'spec': {
                'ports': []}}

        # Making actual call
        self.app.delete(pod.id)

        _drop_network_policies.assert_called_once_with(
            pod.namespace, force=False)
        mock_free_pd.assert_called_once_with(pod.id)
        pc_drop_namespace_mock.assert_called_once_with(pod.namespace,
                                                       force=False)
        remove_ip_mock.assert_called_once_with(pod_id=pod.id, force=False)
        mark_.assert_called_once_with(pod.id)
        self.app.k8squery.delete.assert_called_once_with(
            ['services', 'fs'], ns=pod.namespace)

        remove_ip_mock.reset_mock()
        db_pod = self.fixtures.pod(owner=self.user)
        pod = fake_pod(sid='s', owner=db_pod.owner, id=db_pod.id,
                       set_status=lambda *a, **kw: None,
                       domain='someuser-somepod.somehost.some')
        pc_get_by_id_mock.return_value = pod
        self.app.delete(pod.id)
        self.assertFalse(remove_ip_mock.called)


class TestPodCollectionRunService(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')
        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(helpers.KubeQuery, 'delete')
    @mock.patch.object(helpers.KubeQuery, 'get')
    @mock.patch.object(podcollection.podutils, 'raise_if_failure')
    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(helpers.KubeQuery, 'post')
    def test_pod_run_service(
            self, post_, dbpod_mock, raise_if_failure_mock, mock_get,
            mock_del):
        """
        Test that _run_service generates expected service config
        :type post_: mock.Mock
        """
        # Fake Pod instance
        pod_name = 'bla bla pod'
        pod_id = str(uuid4())
        pod_owner = mock.Mock()
        pod_owner.id = 123
        pod = fake_pod(use_parents=(Pod,), sid='s', name=pod_name, id=pod_id,
                       public_ip='127.0.0.1')
        pod.owner = pod_owner

        pod.containers = [{
            'ports': [{'hostPort': 1000, 'containerPort': 80,
                       'isPublic': True},
                      {'containerPort': 80, 'isPublic': False}],
        }]
        dbpod = mock.Mock()
        dbpod_mock.query.get.return_value = dbpod
        dbpod.get_dbconfig.return_value = {'volumes': []}

        mock_get.return_value = {'items': []}
        # Making actual call
        podcollection.run_service(pod)
        ports, public_ports = podcollection.get_ports(pod)

        calls = post_.mock_calls
        self.assertEqual(len(calls), 3)
        for call in calls:
            name, call_args, call_kwargs = call
            if call_args[0] == ['networkpolicys']:
                self.assertEqual(call_kwargs['ns'], 'n')
                self.assertEqual(call_kwargs['rest'], True)
                policy = json.loads(call_args[1])
                self.assertEqual(
                    policy['spec']['podSelector']['kuberdock-user-uid'],
                    repr(pod_owner.id))
                continue
            self.assertEqual(call_args[0], ['services'])
            self.assertEqual(call_kwargs['ns'], 'n')
            self.assertEqual(call_kwargs['rest'], True)
            service = json.loads(call_args[1])
            self.assertEqual(
                service['spec']['selector']['kuberdock-pod-uid'], pod_id)
            self.assertEqual(
                service['metadata']['labels']['kuberdock-pod-uid'], pod_id)
            service_type = service['metadata']['labels']['kuberdock-type']
            self.assertTrue(
                service_type in (helpers.LOCAL_SVC_TYPE, PUBLIC_SVC_TYPE))
            if service_type == PUBLIC_SVC_TYPE:
                self.assertEqual(service['spec']['ports'], public_ports)
            elif service_type == helpers.LOCAL_SVC_TYPE:
                self.assertEqual(service['spec']['ports'], ports)
            print service


class TestPodcollectionUtils(unittest.TestCase, TestCaseMixin):

    @mock.patch.object(podcollection, 'KubeQuery')
    def test_get_network_policy_api(self, kube_query_mock):
        test_result = 123412341
        kube_query_mock.return_value = test_result
        res = podcollection._get_network_policy_api()
        self.assertEqual(res, test_result)
        kube_query_mock.assert_called_once_with(
            api_version='net.alpha.kubernetes.io/v1alpha1',
            base_url='apis'
        )


class TestPodCollectionMakeNamespace(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'id': 1, 'username': 'bliss'})

        self.user = U()
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')

        self.pod_collection = podcollection.PodCollection(self.user)
        self.test_ns = "user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094"

    @mock.patch.object(podcollection.KubeQuery, 'post')
    def test_pod_make_namespace_is_presented(self, post_):
        """
        Test that _make_namespace do nothing when ns already exists
        :type post_: mock.Mock
        """
        self.pod_collection._get_namespace = mock.Mock(return_value=True)

        # Actual call
        self.pod_collection._make_namespace(self.test_ns)

        self.pod_collection._get_namespace.assert_called_once_with(
            self.test_ns)
        self.assertEquals(post_.called, False)

    @mock.patch.object(podcollection.podutils, 'raise_if_failure')
    @mock.patch.object(podcollection, '_get_network_policy_api')
    @mock.patch.object(podcollection.KubeQuery, 'post')
    def test_pod_make_namespace_new_created(self, post_, np_api_mock, raise_):
        """
        Test that _make_namespace create new ns
        :type post_: mock.Mock
        """
        self.pod_collection._get_namespace = mock.Mock(return_value=None)

        # Actual call
        self.pod_collection._make_namespace(self.test_ns)

        ns_conf = {
            "kind": "Namespace",
            "apiVersion": "v1",
            "metadata": {
                "annotations": {
                    "net.alpha.kubernetes.io/network-isolation": "yes"
                },
                "labels": {"kuberdock-user-uid": "1"},
                "name": self.test_ns
            }
        }
        user_repr = str(self.user.id)
        np_conf = {
            "kind": "NetworkPolicy",
            "spec": {
                "ingress": [{
                    "from": [{
                        "namespaces": {"kuberdock-user-uid": user_repr}
                    }]
                }],
                "podSelector": {"kuberdock-user-uid": user_repr}
            },
            "apiVersion": "net.alpha.kubernetes.io/v1alpha1",
            "metadata": {"name": user_repr}
        }

        self.pod_collection._get_namespace.assert_called_once_with(
            self.test_ns)

        post_.assert_called_once_with(
            ['namespaces'],
            json.dumps(ns_conf),
            ns=False,
            rest=True
        )

        np_api_mock.assert_called_once_with()
        np_api_mock.return_value.post.assert_called_once_with(
            ['networkpolicys'],
            json.dumps(np_conf),
            ns=self.test_ns,
            rest=True
        )


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
                namespace='user-test-some-long-pod-name1-'
                          '8e8843452313cdc9edec704dee6919bb'
            ),
            fake_pod(
                name='Pod with some weird name #3',
                is_deleted=False,
                namespace='ccc6736151b6011c2442c72ddb077be6'
            ),
        ]
        U = type('User', (), {'username': 'user', 'pods': pods})
        self.get_ns_patcher = mock.patch.object(podcollection.PodCollection,
                                                '_get_namespaces')
        self.addCleanup(self.get_ns_patcher.stop)
        self.get_ns_patcher.start()

        self.mock_methods(podcollection.PodCollection, '_get_pods', '_merge')

        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(podcollection.KubeQuery, 'get')
    def test_pod_get_namespaces(self, get_mock):
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
        get_mock.return_value = ns_items

        # Actual call
        get_mock.reset_mock()
        self.get_ns_patcher.stop()
        res = self.pod_collection._get_namespaces()
        self.get_ns_patcher.start()

        get_mock.assert_called_once_with(['namespaces'], ns=False)
        self.assertEquals(res, test_nses[2:])

    @mock.patch.object(podcollection.KubeQuery, 'delete')
    def test_pod_drop_namespace(self, del_):
        """
        Test that _drop_namespace call _del with expected args.
        """
        test_ns = 'some-ns'

        # Actual call
        self.pod_collection._drop_namespace(test_ns)

        del_.assert_called_once_with(
            ['namespaces', test_ns],
            ns=False,
        )


class TestPodCollection(DBTestCase, TestCaseMixin):
    def setUp(self):
        self.user, _ = self.fixtures.user_fixtures()
        self.pods = [{'id': 1, 'name': 'Unnamed-1',
                      'namespace': 'Unnamed-1-namespace-md5',
                      'owner': self.user, 'containers': [],
                      'k8s_status': None,
                      'certificate': None,
                      'volumes': []},
                     {'id': 2, 'name': 'Unnamed-2',
                      'namespace': 'Unnamed-2-namespace-md5',
                      'k8s_status': None,
                      'certificate': None,
                      'owner': self.user, 'containers': [], 'volumes': []}]

        self.pods_output = copy.deepcopy(self.pods)
        for pod in self.pods_output:
            # Some fields excluded from output due to security
            pod.pop('namespace', None)
            pod.pop('owner', None)

        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')

        self.pod_collection = podcollection.PodCollection(self.user)
        self.pod_collection._collection = {}
        for data in self.pods:
            pod = Pod(data)
            self.pod_collection._collection[pod.id, pod.namespace] = pod

    def test_collection_get_as_json(self):
        self.assertItemsEqual(json.loads(self.pod_collection.get()),
                              self.pods_output)
        self.assertEqual(json.loads(self.pod_collection.get(1)),
                         self.pods_output[0])

    def test_collection_get(self):
        self.assertItemsEqual(self.pod_collection.get(as_json=False),
                              self.pods_output)
        self.assertEqual(self.pod_collection.get(1, as_json=False),
                         self.pods_output[0])

    def test_collection_get_by_id_if_id_not_exist(self):
        with self.assertRaises(podcollection.PodNotFound):
            self.pod_collection.get(3)


# TODO: Move common mocks in setUp (refactor this hell)
class TestPodCollectionStartPod(DBTestCase, TestCaseMixin):
    def setUp(self):
        U = type('User', (), {'username': 'user'})

        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge', '_apply_edit')
        self.mock_methods(podcollection.helpers, 'replace_pod_config')

        self.pod_collection = podcollection.PodCollection(U())

        self.test_service_name = 'service-eu53y'
        self.pod_collection._run_service = mock.Mock(
            return_value={'metadata': {'name': self.test_service_name},
                          'spec': {'clusterIP': '1.1.1.1'}})

        self.valid_config = {"valid": "config"}
        self.test_pod = fake_pod(
            use_parents=(mock.Mock,),
            name='unnamed-1',
            public_ip=u'192.168.43.2',
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
        from kubedock.pods.models import IPPool
        self.ippool = IPPool(network='192.168.43.0/29')
        self.ippool.save()

    @mock.patch.object(podcollection, 'db')
    @mock.patch.object(podcollection.PodCollection, 'update')
    @mock.patch.object(podcollection.utils, 'send_event_to_user')
    @mock.patch.object(podcollection.helpers, 'replace_pod_config')
    @mock.patch.object(podcollection, '_try_to_update_existing_rc')
    @mock.patch.object(podcollection.ingress_resource, 'create_ingress')
    @mock.patch.object(podcollection.dns_management,
                       'create_or_update_record')
    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection, 'run_service')
    @mock.patch.object(podcollection.podutils, 'raise_if_failure')
    @mock.patch.object(podcollection.KubeQuery, 'post')
    @mock.patch.object(podcollection.PodCollection, 'has_public_ports')
    def test_pod_prepare_and_run(
            self, has_public_ports_mock, post_mock, raise_if_failure_mock,
            run_service_mock, dbpod_mock, create_or_update_record_mock,
            create_ingress_mock, try_update_rc_mock, replace_pod_config_mock,
            send_event_to_user_mock, podcollection_update_mock, db_mock):
        """
        Test first _start_pod in usual case
        :type post_: mock.Mock
        :type mk_ns: mock.Mock
        :type rif: mock.Mock
        """
        has_public_ports_mock.return_value = True
        create_ingress_mock.return_value = (True, None)
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)
        self.test_pod.kuberdock_resolve = []
        dbpod = mock.Mock()
        dbpod_mock.query.get.return_value = dbpod
        dbpod_config = {'volumes': []}
        dbpod.get_dbconfig.return_value = dbpod_config
        run_service_mock.return_value = (None, None)
        create_or_update_record_mock.return_value = (True, None)
        try_update_rc_mock.return_value = False

        # Actual call
        res = podcollection.prepare_and_run_pod(self.test_pod, dbpod,
                                                dbpod_config)

        run_service_mock.assert_called_once_with(self.test_pod)
        self.test_pod.prepare.assert_called_once_with()
        post_mock.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self.assertTrue(raise_if_failure_mock.called)
        replace_pod_config_mock.assert_called_once_with(
            self.test_pod, dbpod.get_dbconfig.return_value)
        self.test_pod.set_status.assert_called_with(
            POD_STATUSES.pending, send_update=True)
        create_or_update_record_mock.assert_called_once_with(
            self.test_pod.domain, 'A'
        )
        create_ingress_mock.assert_called_once_with(
            self.test_pod.containers,
            self.test_pod.namespace,
            self.test_pod.service,
            self.test_pod.domain,
            self.test_pod.custom_domain,
            self.test_pod.certificate,
        )
        self.assertEqual(res, self.test_pod.as_dict.return_value)
        send_event_to_user_mock.assert_not_called()

        # Test user notification was send in case of some k8s error,
        # and the pod was stopped

        # This is checked to send or not to send notification to a user
        dbpod.is_deleted = False
        raise_if_failure_mock.side_effect = podcollection.PodStartFailure()
        with self.assertRaises(podcollection.PodStartFailure):
            podcollection.prepare_and_run_pod(self.test_pod, dbpod,
                                              dbpod_config)
        podcollection_update_mock.assert_called_once_with(
            self.test_pod.id, {'command': 'stop'}
        )
        self.assertTrue(send_event_to_user_mock.called)

    @mock.patch.object(kapi_pod, 'DBPod')
    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection.helpers, 'set_pod_status')
    @mock.patch.object(podcollection, 'prepare_and_run_pod_task')
    @mock.patch.object(podcollection.PodCollection, '_make_namespace')
    @mock.patch.object(podcollection.PodCollection, '_node_available_for_pod')
    def test_pod_start(
            self, node_available_mock, mk_ns, run_pod_mock, set_pod_status,
            db_pod_mock, DBPod):
        """
        Test first _start_pod for pod without ports
        :type post_: mock.Mock
        """
        pod = fake_pod(
            use_parents=(Pod,),
            name='unnamed-1',
            is_deleted=False,
            status=POD_STATUSES.stopped,
            kind='replicationcontrollers',
            namespace="user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094",
            containers=[{
                'ports': [],
                'name': '2dbgdc',
                'state': POD_STATUSES.stopped,
            }]
        )

        db_pod = mock.Mock(id=pod.id, status=POD_STATUSES.stopped)
        db_pod_mock.query.get.return_value = db_pod
        db_config = {}
        db_pod.get_dbconfig.return_value = db_config

        # Actual call
        self.pod_collection._start_pod(pod)

        node_available_mock.assert_called_once_with(pod)
        mk_ns.assert_called_once_with(pod.namespace)
        run_pod_mock.delay.assert_called_once_with(pod, db_pod.id, db_config)
        self.assertEqual(pod.status, POD_STATUSES.preparing)

    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection.PodCollection, '_node_available_for_pod')
    def test_start_pod_failure(self, node_available_mock, db_pod_mock):
        """
        Test _start_pod with no available nodes
        :type post_: mock.Mock
        """
        pod = mock.Mock()
        node_available_mock.return_value = False

        with self.assertRaisesRegexp(
                NoSuitableNode,
                "There are no suitable nodes for the pod.*"):
            # Actual call
            self.pod_collection._start_pod(pod)

        node_available_mock.assert_called_once_with(pod)

    @mock.patch.object(podcollection, 'DBPod')
    def test_node_available_for_pod_first(self, dbpod_mock):
        """
        Test _node_available_for_pod: service pod
        """
        pod = mock.Mock()
        pod.kube_type = 1
        db_pod = mock.Mock()
        db_pod.is_service_pod = True
        dbpod_mock.query.get.return_value = db_pod

        # Actual call
        res = self.pod_collection._node_available_for_pod(pod)
        self.assertTrue(res)

    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection.node_utils, 'node_status_running')
    @mock.patch.object(podcollection, 'Node')
    def test_node_available_for_pod_second(
            self, dbnode_mock, node_status_mock, dbpod_mock):
        """
        Test _node_available_for_pod: pinned node
        """
        pod = mock.Mock()
        db_pod = mock.Mock()
        db_pod.is_service_pod = False
        dbpod_mock.query.get.return_value = db_pod
        node_hostname = 'mock-node'
        db_pod.pinned_node = node_hostname
        db_node = mock.Mock()
        dbnode_mock.get_by_name.return_value = db_node
        node_status_mock.return_value = True

        # Actual call #1
        res = self.pod_collection._node_available_for_pod(pod)
        node_status_mock.assert_called_with(db_node)
        self.assertTrue(res)

        node_status_mock.return_value = False
        # Actual call #2
        res = self.pod_collection._node_available_for_pod(pod)
        node_status_mock.assert_called_with(db_node)
        self.assertFalse(res)

    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection.node_utils, 'get_nodes_collection')
    def test_node_available_for_pod_third(self, get_nodes_mock, dbpod_mock):
        """
        Test _node_available_for_pod: no pinned node
        """
        pod = mock.Mock()
        pod.kube_type = 1
        db_pod = mock.Mock()
        db_pod.pinned_node = None
        db_pod.is_service_pod = False
        dbpod_mock.query.get.return_value = db_pod

        nodes_collection = [
            {'id': str(uuid4()), 'status': NODE_STATUSES.deletion},
            {'id': str(uuid4()), 'status': NODE_STATUSES.troubles},
            {'id': str(uuid4()), 'status': NODE_STATUSES.running}
        ]
        get_nodes_mock.return_value = nodes_collection

        # Actual call #1
        res = self.pod_collection._node_available_for_pod(pod)
        get_nodes_mock.assert_called_with(kube_type=pod.kube_type)
        self.assertTrue(res)

        nodes_collection = [
            {'id': str(uuid4()), 'status': NODE_STATUSES.deletion},
            {'id': str(uuid4()), 'status': NODE_STATUSES.troubles},
            {'id': str(uuid4()), 'status': NODE_STATUSES.troubles}
        ]
        get_nodes_mock.return_value = nodes_collection

        # Actual call #2
        res = self.pod_collection._node_available_for_pod(pod)
        get_nodes_mock.assert_called_with(kube_type=pod.kube_type)
        self.assertFalse(res)

    @mock.patch.object(podcollection, '_try_to_update_existing_rc')
    @mock.patch.object(podcollection.ingress_resource, 'create_ingress')
    @mock.patch.object(podcollection.dns_management,
                       'create_or_update_record')
    @mock.patch.object(podcollection, 'run_service')
    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection.KubeQuery, 'post')
    @mock.patch.object(podcollection.PodCollection, 'has_public_ports')
    def test_pod_prepare_and_run_task_second_start(
            self, has_public_ports_mock, post_, dbpod_mock, run_service_mock,
            create_or_update_record_mock, create_ingress_mock,
            try_update_rc_mock):
        """
        Test second _start_pod in usual case
        :type post_: mock.Mock
        """

        has_public_ports_mock.return_value = True
        create_ingress_mock.return_value = (True, None)
        dbpod_mock.query.get().get_dbconfig.return_value = {
            'volumes': [], 'service': self.test_service_name}
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)
        self.test_pod.kuberdock_resolve = []

        dbpod = mock.Mock()
        dbpod_mock.query.get.return_value = dbpod
        dbpod_config = {
            'volumes': [], 'service': self.test_service_name
        }
        dbpod.get_dbconfig.return_value = dbpod.config
        run_service_mock.return_value = (None, None)
        create_or_update_record_mock.return_value = (True, None)
        try_update_rc_mock.return_value = False

        # Actual call
        res = podcollection.prepare_and_run_pod(self.test_pod, dbpod,
                                                dbpod_config)

        self.test_pod.prepare.assert_called_once_with()
        post_.assert_called_once_with(
            [self.test_pod.kind], json.dumps(self.valid_config), rest=True,
            ns=self.test_pod.namespace)
        self.test_pod.set_status.assert_called_with(
            POD_STATUSES.pending, send_update=True)
        create_or_update_record_mock.assert_called_once_with(
            self.test_pod.domain, 'A'
        )
        create_ingress_mock.assert_called_once_with(
            self.test_pod.containers,
            self.test_pod.namespace,
            self.test_pod.service,
            self.test_pod.domain,
            self.test_pod.custom_domain,
            self.test_pod.certificate,
        )
        self.assertEqual(res, self.test_pod.as_dict.return_value)

    def test_has_public_ports(self):
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
        self.assertTrue(self.pod_collection.has_public_ports(test_conf))
        self.assertFalse(self.pod_collection.has_public_ports(test_conf2))

    @mock.patch.object(pod_domains, 'validate_domain_reachability')
    @mock.patch.object(podcollection.PodCollection, '_make_namespace')
    @mock.patch.object(podcollection, 'prepare_and_run_pod_task')
    @mock.patch.object(podcollection, 'get_replicationcontroller')
    @mock.patch.object(podcollection, 'IpState')
    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection.dns_management, 'is_domain_system_ready')
    @mock.patch.object(podcollection, 'db')
    def test_apply_edit_called(self, mock_db, is_domain_system_ready_mock,
                               DBPod, IpState, get_replicationcontroller,
                               prepare_and_run_pod_task, _make_namespace,
                               domain_check_mock):
        domain_check_mock.return_value = True
        config = {'volumes': [], 'service': self.test_service_name}
        DBPod.query.get().get_dbconfig.return_value = config
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)
        self.pod_collection._apply_edit.return_value = (self.test_pod, config)
        is_domain_system_ready_mock.return_value = (True, None)
        mock_db.session.commit = mock.Mock()
        self.pod_collection._start_pod(
            self.test_pod, {'commandOptions': {'applyEdit': True}})
        self.pod_collection._apply_edit.assert_called_once_with(
            self.test_pod, DBPod.query.get(), config, internal_edit=False)
        mock_db.session.commit.assert_called_with()


class TestPodCollectionStopPod(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        U = type('User', (), {'username': 'user'})
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')
        self.pod_collection = podcollection.PodCollection(U())

    @responses.activate
    @mock.patch.object(podcollection.PersistentDisk, 'free')
    @mock.patch.object(podcollection.scale_replicationcontroller_task,
                       'apply_async')
    def test_pod_normal_stop(self, mk_scale_rc, free_pd_mock):
        """
        Test _stop_pod in usual case
        :type del_: mock.Mock
        :type rif: mock.Mock
        """
        mock_k8s_ingress_endpoints()

        pod = fake_pod(
            use_parents=(mock.Mock,),
            status=POD_STATUSES.running,
            namespace="user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094",
            containers=[{
                'name': '2dbgdc',
                'state': POD_STATUSES.running,
            }]
        )

        # Actual call
        res = self.pod_collection._stop_pod(pod)

        pod.set_status.assert_called_once_with(
            POD_STATUSES.stopping, send_update=True)
        mk_scale_rc.assert_called_once_with((pod.id,))

        free_pd_mock.assert_called_once_with(pod.id)

        # pod is not "stopped" yet, only "stopping",
        # so containers are still "running"
        self.assertEqual(pod.containers[0]['state'], POD_STATUSES.running)
        self.assertEqual(res, pod.as_dict.return_value)

    @responses.activate
    @mock.patch.object(podcollection.PersistentDisk, 'free')
    @mock.patch.object(podcollection, 'DBPod')
    @mock.patch.object(podcollection, 'scale_replicationcontroller')
    @mock.patch.object(podcollection, 'db')
    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    @mock.patch.object(podcollection, 'wait_pod_status')
    def test_pod_stop_unpaid(self, wait_pod_status, _get_by_id, mock_db,
                             scale_replicationcontroller,
                             dbpod_mock, free_pd_mock):
        """
        Test stop_unpaid in usual case
        """
        mock_k8s_ingress_endpoints()
        pod = fake_pod(
            id='119fd339-f12c-4be3-bfa1-2e82001d0811',
            use_parents=(mock.Mock,),
            status=POD_STATUSES.running,
            namespace="user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094",
            containers=[{
                'name': '2dbgdc',
                'state': POD_STATUSES.running,
            }]
        )
        pod2 = fake_pod(
            id='119fd339-f12c-4be3-bfa1-2e82001d0811',
            use_parents=(mock.Mock,),
            status=POD_STATUSES.stopped,
            namespace="user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094",
            containers=[{
                'name': '2dbgdc',
                'state': POD_STATUSES.stopped,
            }]
        )

        def fake_wait_pod_status(pod_id, *args, **kwargs):
            return {pod.id: pod for pod in [pod, pod2]}[pod_id]

        wait_pod_status.side_effect = fake_wait_pod_status

        _get_by_id.return_value = pod2

        # Actual call
        self.pod_collection.stop_unpaid(pod, block=True)

        pod.set_status.assert_called_once_with(
            POD_STATUSES.stopping, send_update=True)

        scale_replicationcontroller.assert_called_once_with(pod.id)

        free_pd_mock.assert_called_once_with(pod.id)

        wait_pod_status.assert_called_once_with(
            pod.id, POD_STATUSES.stopped,
            error_message=(
                u'During restart, Pod "{0}" did not become '
                u'stopped after a given timeout. It may become '
                u'later.'.format(pod.name)))

        # TODO: "Pod is already stopped" test


class TestPodCollectionPreprocessNewPod(DBTestCase, TestCaseMixin):
    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge', 'get_secrets',
                          '_check_trial')
        self.mock_methods(podcollection,
                          'extract_secrets', 'fix_relative_mount_paths')
        podcollection.extract_secrets.return_value = set()

        self.user, _ = self.fixtures.user_fixtures()
        self.params = {'name': 'nginx', 'containers': []}
        self.pod_collection = podcollection.PodCollection(self.user)

    @mock.patch.object(podcollection.PodCollection, '_save_k8s_secrets',
                       mock.Mock())
    @mock.patch.object(podcollection.Image, 'check_containers')
    def test_check_containers_called(self, check_):
        old_secret = ('username-1', 'password-1', 'regist.ry')
        same_secret = ('username-2', 'password-2', 'regist.ry')
        new_secret = ('username-3', 'password-3', 'regist.ry')
        containers = [
            {'image': 'wncm/test_image:4', 'name': 'a', 'args': ['nginx'],
             'secret': dict(zip(['username', 'password'], same_secret))},
            {'image': 'quay.io/wncm/test_image', 'name': 'b',
             'args': ['nginx'],
             'secret': dict(zip(['username', 'password'], new_secret))},
        ]
        params = dict(self.params, containers=containers)
        podcollection.extract_secrets.return_value = set([new_secret,
                                                          same_secret])
        _, secrets = self.pod_collection._preprocess_new_pod(params)
        podcollection.extract_secrets.assert_called_once_with(
            params['containers'])
        self.assertItemsEqual(secrets, [new_secret, same_secret])
        check_.assert_called_once_with(containers, secrets)

        # edit pod
        check_.reset_mock()
        self.pod_collection.get_secrets.return_value = {
            'secret-name-1': old_secret,
            'secret-name-2': same_secret,
        }
        original_pod = 'original-pod'
        _, secrets = self.pod_collection._preprocess_new_pod(
            params, original_pod=original_pod)
        self.pod_collection.get_secrets.assert_called_once_with(original_pod)
        self.assertItemsEqual(secrets, [old_secret, same_secret, new_secret])
        check_.assert_called_once_with(containers, secrets)

    def test_check_trial_called(self):
        self.pod_collection._preprocess_new_pod(self.params)
        self.pod_collection._check_trial.assert_called_once_with(
            self.params['containers'], original_pod=None)

        self.pod_collection._check_trial.reset_mock()
        self.pod_collection._preprocess_new_pod(self.params, skip_check=True)
        self.assertFalse(self.pod_collection._check_trial.called)

    def test_fix_relative_mount_paths(self):
        self.pod_collection._preprocess_new_pod(self.params)
        podcollection.fix_relative_mount_paths.assert_called_once_with(
            self.params['containers'])


class TestPodCollectionAdd(DBTestCase, TestCaseMixin):
    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge', '_save_pod', '_check_trial',
                          '_make_namespace', '_preprocess_new_pod')
        self.mock_methods(podcollection, 'Pod')

        self.user, _ = self.fixtures.user_fixtures(
            role_id=Role.by_rolename('TrialUser').id)
        pod_id = str(uuid4())
        podcollection.Pod.return_value.namespace = pod_id
        podcollection.Pod.return_value.owner = self.user
        podcollection.Pod.return_value.id = pod_id

        self.name = 'nginx'
        self.params = {'name': self.name, 'containers': ()}
        self.namespace = pod_id

        podcollection.PodCollection._preprocess_new_pod.return_value = (
            self.params, ())

        self.pod_collection = podcollection.PodCollection(self.user)

    @mock.patch.object(podcollection.PodCollection, '_make_namespace')
    def test_make_namespace_called(self, make_namespace_):
        self.pod_collection.add(self.params)
        make_namespace_.assert_called_once_with(self.namespace)

    @mock.patch.object(podcollection, 'extract_secrets')
    @mock.patch.object(podcollection.PodCollection, '_save_k8s_secrets')
    def test_save_k8s_secret_called(self, save_k8s_secrets_, extract_secrets_):
        secrets = [('test_user', 'test_password', mock.ANY),
                   ('test_user2', 'test_password2', mock.ANY)]
        podcollection.PodCollection._preprocess_new_pod.return_value = (
            self.params, secrets)
        extract_secrets_.return_value = set(secrets)

        self.pod_collection.add(self.params, skip_check=True)
        save_k8s_secrets_.assert_called_once_with(secrets, self.namespace)

    @mock.patch.object(podcollection, 'uuid4')
    def test_pod_create_called(self, uuid4_):
        uuid4_.return_value = self.namespace
        self.pod_collection.add(self.params)
        podcollection.Pod.assert_called_once_with({
            'id': uuid4_.return_value,
            'name': self.name,
            'namespace': self.namespace,
            'sid': mock.ANY,
            'status': 'stopped',
            'containers': (),
            'volumes': [],
            'public_access_type': 'public_ip'
        })

    def test_pod_compose_persistent_called(self):
        self.pod_collection.add(self.params)
        pod_ = podcollection.Pod.return_value
        pod_.compose_persistent.assert_called_once_with(reuse_pv=True)

    def test_save_pod_called(self):
        self.pod_collection.add(self.params)
        self.assertTrue(self.pod_collection._save_pod.called)

    @mock.patch('kubedock.kapi.podcollection.uuid4')
    def test_preprocess_new_pod_called(self, uuid4_):
        uuid4_.return_value = self.namespace
        self.pod_collection.add(self.params)
        self.pod_collection._preprocess_new_pod.assert_called_once_with(
            self.params, skip_check=False)

    def test_pod_forge_dockers_called(self):
        self.pod_collection.add(self.params)
        pod_ = podcollection.Pod.return_value
        self.assertTrue(pod_.forge_dockers.called)

    @mock.patch.object(podcollection.PodCollection, 'has_public_ports')
    def test_pod_has_public_ports_called(self, _mock):
        self.pod_collection.add(self.params)
        self.assertTrue(_mock.called)

    def test_pod_as_dict_called(self):
        self.pod_collection.add(self.params)
        pod_ = podcollection.Pod.return_value
        self.assertTrue(pod_.as_dict.called)

    @mock.patch.object(podcollection.PodCollection, '_add_pod')
    def test_dry_run(self, _add_pod):
        self.assertIs(self.pod_collection.add(self.params, dry_run=True), True)
        self.assertFalse(_add_pod.called)


class TestPodCollectionUpdate(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge',
                          '_start_pod', '_stop_pod')

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

        def patch_method(method):
            return mock.patch.object(
                podcollection.PodCollection, method)

        with patch_method('_start_pod') as start_pod_mock:
            pod_data = {'command': 'start'}
            self.pod_collection.update(pod_id, pod_data)
            start_pod_mock.assert_called_once_with(pod, {})

        with patch_method('_stop_pod') as stop_pod_mock:
            pod_data = {'command': 'stop'}
            self.pod_collection.update(pod_id, pod_data)
            stop_pod_mock.assert_called_once_with(pod, {})

        with patch_method('_change_pod_config') as change_pod_config_mock:
            pod_data = {'command': 'change_config'}
            self.pod_collection.update(pod_id, pod_data)
            change_pod_config_mock.assert_called_once_with(pod, {})

        get_by_id_mock.assert_has_calls([mock.call(pod_id)] * 3)


@unittest.skip('Not supported')
class TestPodCollectionDoContainerAction(unittest.TestCase, TestCaseMixin):
    # some available actions
    actions = ('start', 'stop', 'rm')

    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')

        U = type('User', (), {'username': '4u5hfee'})
        self.pod_collection = podcollection.PodCollection(U())

    def _create_request(self):
        return choice(self.actions), {
            'nodeName': str(uuid4()),
            'containers': ','.join(str(uuid4()) for i in range(
                randrange(1, 10))),
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
    def test_run_ssh_command_called(self, send_event_mock,
                                    run_ssh_command_mock):
        """ Check result. Check that `run_ssh_command` has right calls. """
        run_ssh_command_mock.return_value = status, message = 0, 'ok'

        action, data = self._create_request()
        result = self.pod_collection._do_container_action(action, data)

        self.assertDictEqual(
            result,
            {container: message for container in data['containers'].split(',')}
        )
        run_ssh_command_mock.assert_has_calls(
            [mock.call(data['nodeName'], mock.ANY)
             for _ in data['containers'].split(',')]
        )

    @mock.patch('kubedock.kapi.podcollection.run_ssh_command')
    @mock.patch('kubedock.kapi.podcollection.send_event')
    def test_send_event_called(self, send_event_mock, run_ssh_command_mock):
        """ When "start" or "stop" called, event "pull_pod_state"
        should be sent """
        run_ssh_command_mock.return_value = status, message = 0, 'ok'

        action, data = self._create_request()
        self.pod_collection._do_container_action('start', data)
        send_event_mock.assert_has_calls(
            [mock.call('pull_pod_state', message)
             for _ in data['containers'].split(',')]
        )
        action, data = self._create_request()
        self.pod_collection._do_container_action('stop', data)
        send_event_mock.assert_has_calls(
            [mock.call('pull_pod_state', message)
             for _ in data['containers'].split(',')]
        )

    @mock.patch('kubedock.kapi.podcollection.run_ssh_command')
    @mock.patch('kubedock.kapi.podcollection.send_event')
    def test_docker_error(self, send_event_mock, run_ssh_command_mock):
        """ Raise an error, if exit status of run_ssh_command
        is not equal 0 """
        run_ssh_command_mock.return_value = status, message = 1, 'sh-t happens'

        action, data = self._create_request()
        with self.assertRaises(Exception):
            self.pod_collection._do_container_action(action, data)
        run_ssh_command_mock.assert_called_once_with(data['nodeName'],
                                                     mock.ANY)


class TestPodCollectionGetPods(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        def _init_podcollection(self, owner=None):
            self.owner = owner
            self.k8squery = podcollection.KubeQuery()

        self.mock_methods(
            podcollection.PodCollection, '_get_namespaces', '_merge',
            __init__=_init_podcollection
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

    @mock.patch.object(podcollection.KubeQuery, 'get')
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
            for api in ('pods', 'replicationcontrollers')
        ])

    @mock.patch('kubedock.kapi.podcollection.Pod')
    @mock.patch.object(podcollection.KubeQuery, 'get')
    def test_replication(self, get_mock, PodMock):
        """
        If replication controller manages more then one pod,
        _get_pods should save only one of them in _collection
        """
        namespace = str(uuid4())
        get_mock.side_effect = lambda res, ns=None: {  # fake kubernates API
            'pods': {'items': [{'metadata': {'labels': {'name': name}}}
                               for name in ('pod1', 'pod1', 'pod1', 'pod2',
                                            'pod2')]},
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
    @mock.patch.object(podcollection.KubeQuery, 'get')
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
        labels = {str(uuid4()): str(uuid4())
                  for i in range(randrange(1, 10))}
        selector = {str(uuid4()): str(uuid4())
                    for i in range(randrange(1, 10))}

        self.assertFalse(podcollection.PodCollection._is_related(
            labels, selector))

        labels_related = labels.copy()
        # If all key/value pairs in selector exist in labels,
        # then object is related
        labels_related.update(selector)
        self.assertTrue(podcollection.PodCollection._is_related(
            labels_related, selector))

        # empty selector will match any object
        self.assertTrue(podcollection.PodCollection._is_related(labels, {}))

        # if labels or selector is None, object is not related
        self.assertFalse(podcollection.PodCollection._is_related(labels, None))
        self.assertFalse(podcollection.PodCollection._is_related(
            None, selector))
        self.assertFalse(podcollection.PodCollection._is_related(None, None))


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
                       'direct_access': '{}',
                       'kube_id': randrange(3),
                       'config': json.dumps({'name': pod_id,
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

    @mock.patch.object(podcollection.helpers, 'fetch_pods')
    def test_pods_fetched(self, fetch_pods_mock):
        """ _merge will fetch pods from db """
        fetch_pods_mock.return_value = []
        pod_collection = podcollection.PodCollection()
        pod_collection._collection = {}
        pod_collection._merge()
        fetch_pods_mock.assert_called_once_with(users=True)

    @mock.patch('kubedock.kapi.podcollection.Pod')
    @mock.patch.object(podcollection.helpers, 'fetch_pods')
    def test_pods_in_db_only(self, fetch_pods_mock, pod_mock):
        """ If pod exists in db only, then forge_dockers and add in
        _collection """
        generated_pods = []

        def pod_init_mock(data):
            pod = mock.create_autospec(Pod, instance=True)
            pod.__dict__.update(data)
            # pod.name = data['name']
            pod.containers = []
            pod.k8s_status = None
            generated_pods.append(pod)
            return pod

        pod_mock.side_effect = pod_init_mock

        pod_model_instances = self._get_fake_pod_model_instances()
        fetch_pods_mock.return_value = pod_model_instances

        pod_collection = podcollection.PodCollection()
        pod_collection._collection = {}
        pod_collection._merge()

        # [(args, kwargs),..] > [args, args,..]
        self.assertItemsEqual(
            zip(*pod_mock.call_args_list)[0],
            [(json.loads(pod.config),) for pod in pod_model_instances]
        )
        for pod in generated_pods:
            pod.forge_dockers.assert_called_once_with()

        self.assertItemsEqual(
            pod_collection._collection.iterkeys(),
            ((pod.id, pod.namespace) for pod in pod_model_instances)
        )

    @mock.patch.object(podcollection.podutils, 'merge_lists')
    @mock.patch.object(podcollection.helpers, 'fetch_pods')
    def test_pods_in_db_and_kubernetes(self, fetch_pods_mock,
                                       merge_lists_mock):
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
                'k8s_status': None,
                'containers': []
            })
            for pod in pod_model_instances
        }

        pod_collection = podcollection.PodCollection()
        pod_collection._collection = pods_in_kubernetes.copy()
        pod_collection._merge()

        self.assertEqual(len(pod_collection._collection), pods_total)
        # check that data from db was copied in pod
        for pod in pod_model_instances:
            pod_in_collection = pod_collection._collection[pod.id,
                                                           pod.namespace]
            self.assertEqual(pod.id, pod_in_collection.id)
            self.assertEqual(pod.kube_id, pod_in_collection.kube_type)
        # check that containers lists were merged using "name" as key
        merge_lists_mock.assert_has_calls([
            mock.call([], [], 'name')
            for i in range(pods_total)
        ])


@mock.patch.object(podcollection.SystemSettings, 'get_by_name',
                   return_value=10)
class TestPodCollectionCheckTrial(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_merge', '_get_pods')
        U = type('User', (), {'username': '4u5hfee'})
        self.user = U()

    def pod_factory(self, id, kubes):
        return type('Pod', (), {
            'is_deleted': False,
            'kubes': kubes,
            'id': id})()

    @mock.patch.object(podcollection.podutils, 'raise_')
    def test_enough_kubes(self, raise_mock, systemSettings_mock):
        """ user is trial and have enough kubes for a new pod """
        self.user.is_trial = lambda: True
        self.user.pods = [self.pod_factory(None, 5)]
        containers = [{'kubes': 2}, {'kubes': 2}, {'kubes': 1}]
        podcollection.PodCollection(self.user)._check_trial(containers)
        self.assertFalse(raise_mock.called)

    @mock.patch.object(podcollection.podutils, 'raise_')
    def test_not_enough_kubes(self, raise_mock, systemSettings_mock):
        """ user is trial and don't have enough kubes for a new pod """
        self.user.is_trial = lambda: True
        self.user.pods = [self.pod_factory(None, 5)]
        containers = [{'kubes': 2}, {'kubes': 4}]
        podcollection.PodCollection(self.user)._check_trial(containers)
        raise_mock.assert_called_once_with(mock.ANY)

    @mock.patch.object(podcollection.podutils, 'raise_')
    def test_user_is_not_trial(self, raise_mock, systemSettings_mock):
        self.user.is_trial = lambda: False
        self.user.pods = [type('Pod', (), {'is_deleted': False, 'kubes': 5})]
        containers = [{'kubes': 2}, {'kubes': 4}]
        podcollection.PodCollection(self.user)._check_trial(containers)
        self.assertFalse(raise_mock.called)

    @mock.patch.object(podcollection.podutils, 'raise_')
    def test_add_kubes_to_exists_pod_enough(self, raise_mock,
                                            systemSettings_mock):
        """ user is trial and have enough kubes for a exists pod """
        self.user.is_trial = lambda: True
        edit_pod = self.pod_factory('bbbbbbbb-72b4-49c0-869d-34d87fb4edf6', 3)
        pods = type("Pods", (), {
            'filter': lambda q, a: filter(
                lambda x: not a.compare(DBPod.id != x.id), [
                    self.pod_factory(
                        'aaaaaaaa-72b4-49c0-869d-34d87fb4edf6', 2),
                    edit_pod
                ])})

        self.user.pods = pods()

        containers = [{'kubes': 3}, {'kubes': 3}, {'kubes': 2}]
        podcollection.PodCollection(self.user)._check_trial(
            containers, original_pod=edit_pod)
        self.assertFalse(raise_mock.called)

    @mock.patch.object(podcollection.podutils, 'raise_')
    def test_add_kubes_to_exists_pod_not_enough(self, raise_mock,
                                                systemSettings_mock):
        """ user is trial and don't have enough kubes for a exists pod """
        self.user.is_trial = lambda: True

        edit_pod = self.pod_factory('bbbbbbbb-72b4-49c0-869d-34d87fb4edf6', 3)
        pods = type("Pods", (), {
            'filter': lambda q, a: filter(
                lambda x: not a.compare(DBPod.id != x.id), [
                    self.pod_factory(
                        'aaaaaaaa-72b4-49c0-869d-34d87fb4edf6', 3),
                    edit_pod
                ])})

        self.user.pods = pods()

        containers = [{'kubes': 3}, {'kubes': 3}, {'kubes': 2}]
        podcollection.PodCollection(self.user)\
            ._check_trial(containers, original_pod=edit_pod)
        raise_mock.assert_called_once_with(mock.ANY)


class TestPodCollectionGetSecrets(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')

        U = type('User', (), {'username': 'oergjh'})
        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(kapi_pod.K8sSecretsClient, 'list')
    def test_get_secrets(self, get_mock):
        """Get secrets from kubernetes"""
        pod = fake_pod(use_parents=(Pod,), id=str(uuid4()),
                       secrets=('secret-1', 'secret-2'),
                       namespace=str(uuid4()))
        get_mock.return_value = {
            'items': [
                {
                    'data': {
                        '.dockercfg': (
                            'eyJxdWF5LmlvIjogeyJhdXRoIjogImRYTmxjbTVoYldVeE9uQ'
                            'mhjM04zYjNKa01RPT0iLCAiZW1haWwiOiAiYUBhLmEiIH19')
                    },
                    'metadata': {'name': 'secret-1',
                                 'namespace': pod.namespace},
                    'type': 'kubernetes.io/dockercfg'
                },
                {
                    'data': {
                        '.dockercfg': (
                            'eyJxdWF5LmlvIjogeyJhdXRoIjogImRYTmxjbTVoYldVeE9uQ'
                            'mhjM04zYjNKa01RPT0iLCAiZW1haWwiOiAiYUBhLmEiIH19')
                    },
                    'metadata': {'name': 'secret-2',
                                 'namespace': pod.namespace},
                    'type': 'kubernetes.io/dockercfg'
                }
            ]
        }
        username, password, registry = 'username1', 'password1', 'quay.io'

        secrets = self.pod_collection.get_secrets(pod)

        get_mock.assert_called_once_with(namespace=pod.namespace)
        self.assertEqual(secrets, {'secret-1': (username, password, registry),
                                   'secret-2': (username, password, registry)})

    @mock.patch.object(podcollection.KubeQuery, 'get')
    def test_secret_not_found(self, get_mock):
        """
        If secret was not found in kubernetes,
        podcollection.PodCollection.get_secrets must raise an APIError
        """
        pod = fake_pod(use_parents=(Pod,), id=str(uuid4()),
                       secrets=('secret-1', 'secret-2'),
                       namespace=str(uuid4()))
        get_mock.return_value = {'kind': 'Status',
                                 'status': 'Failure',
                                 'message': 'smth\'s wrong'}

        with self.assertRaises(APIError):
            self.pod_collection.get_secrets(pod)


@mock.patch.object(podcollection.PodCollection, '_get_by_id')
class TestPodCollectionCheckUpdates(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')

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

    @mock.patch.object(podcollection.PodCollection, 'get_secrets')
    @mock.patch.object(podcollection.Image, 'get_id', autospec=True)
    def test_with_secrets(self, get_image_id_mock, get_secrets_mock,
                          get_by_id_mock):
        """Request secrets from kubernetes, format and pass to get_id"""
        Image = podcollection.Image
        image, image_id, container_id = (
            'nginx', 'ceab60537ad2d', 'oduhrg94her4')

        secrets_full = {'secret-1': ('user1', 'password', 'regist.ry'),
                        'secret-2': ('user2', 'p-0', 'quay.io')}
        pod = fake_pod(id=str(uuid4()), secrets=secrets_full.keys(),
                       containers=[{'image': image, 'imageID': image_id,
                                    'name': container_id}])

        get_by_id_mock.return_value = pod
        get_secrets_mock.return_value = secrets_full
        get_image_id_mock.return_value = image_id

        self.pod_collection.check_updates(pod.id, container_id)

        get_secrets_mock.assert_called_once_with(pod)
        get_image_id_mock.assert_called_once_with(Image(image),
                                                  secrets_full.values())

    @mock.patch.object(podcollection.Image, 'get_id', autospec=True)
    @mock.patch.object(podcollection.Pod, 'get_secrets')
    def test_check_updates(self, get_secrets_mock, get_image_id_mock,
                           get_by_id_mock):
        """
        check_updates must return True if image_id in registry != imageID in
        pod spec. otherwise (if ids are equal) - return False.
        Raise APIError if it couldn't get image_id from registry
        """
        Image = podcollection.Image
        image, image_id, container_id = 'nginx', 'ceab60537ad2d', \
                                        'oduhrg94her4'
        pod = fake_pod(
            use_parents=(Pod,), id=str(uuid4()), secrets=(),
            containers=[
                {'image': image, 'imageID': image_id, 'name': container_id}
            ])
        get_by_id_mock.return_value = pod

        get_image_id_mock.return_value = None
        with self.assertRaises(APIError):
            self.pod_collection.check_updates(pod.id, container_id)
        get_image_id_mock.assert_called_once_with(Image(image), [])

        get_image_id_mock.reset_mock()
        get_image_id_mock.return_value = image_id
        self.assertFalse(self.pod_collection.check_updates(pod.id,
                                                           container_id))
        get_image_id_mock.assert_called_once_with(Image(image), [])

        get_image_id_mock.reset_mock()
        get_image_id_mock.return_value = 'new_id'
        self.assertTrue(self.pod_collection.check_updates(pod.id,
                                                          container_id))
        get_image_id_mock.assert_called_once_with(Image(image), [])


class TestPodCollectionUpdateContainer(unittest.TestCase, TestCaseMixin):
    def setUp(self):
        # mock all these methods to prevent any accidental calls
        self.mock_methods(podcollection.PodCollection, '_get_namespaces',
                          '_get_pods', '_merge')
        U = type('User', (), {'username': 'oergjh'})
        self.pod_collection = podcollection.PodCollection(U())

    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    @mock.patch.object(podcollection.PodCollection, '_stop_pod')
    @mock.patch.object(podcollection.PodCollection, '_start_pod')
    def test_update_container(self, start_pod_mock, stop_pod_mock,
                              get_by_id_mock):
        """update_container must restart pod"""
        pod_id, container_id = str(uuid4()), str(uuid4())
        pod = fake_pod(id=pod_id)
        get_by_id_mock.return_value = pod

        self.pod_collection.update_container(pod_id, container_id)
        get_by_id_mock.assert_called_once_with(pod_id)
        stop_pod_mock.assert_called_once_with(pod, block=True)
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
        podcollection.PodCollection._remove_public_ip(pod_id=self.pod.id,
                                                      ip=int(self.ip))
        self._check_removed_and_retrun_back()


class TestPodComposePersistent(DBTestCase):
    @mock.patch.object(kapi_pod.pstorage, 'get_storage_class', mock.Mock())
    def test_defaults(self):
        self.user, _ = self.fixtures.user_fixtures()
        self.db.session.add(podcollection.PersistentDisk(
            name='present-2', owner=self.user, size=2
        ))
        self.db.session.commit()

        volumes_in = [
            {'name': 'vol-1', 'localStorage': True},
            {'name': 'vol-2', 'persistentDisk': {'pdName': 'wncm',
                                                 'pdSize': 5}},
            {'name': 'vol-3', 'persistentDisk': {'pdName': 'default-1'}},
            {'name': 'vol-4', 'persistentDisk': {'pdName': 'present-2',
                                                 'pdSize': 2}},
        ]
        volumes_public = [
            {'name': 'vol-1', 'localStorage': True},
            {'name': 'vol-2', 'persistentDisk': {'pdName': 'wncm',
                                                 'pdSize': 5}},
            {'name': 'vol-3', 'persistentDisk': {'pdName': 'default-1',
                                                 'pdSize': 1}},
            {'name': 'vol-4', 'persistentDisk': {'pdName': 'present-2',
                                                 'pdSize': 2}},
        ]
        pod = Pod({'id': str(uuid4()),
                   'owner': self.user,
                   'volumes': volumes_in,
                   'containers': [{'name': 'nginx', 'image': 'nginx'}]})
        pod.compose_persistent()
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

    @mock.patch.object(podcollection.helpers, 'get_pod_config')
    @mock.patch.object(podcollection.podutils, 'raise_if_failure')
    @mock.patch.object(podcollection.helpers, 'replace_pod_config')
    @mock.patch.object(podcollection.KubeQuery, 'put')
    @mock.patch.object(podcollection.PodCollection, '_get_by_id')
    def test_pin_pod_to_node(self, get_by_id, put, rep_config, raise_fail,
                             get_pod_config_mock):
        get_by_id.return_value = self.test_pod
        get_pod_config_mock.return_value = {'node': None}
        self.test_pod.prepare = mock.Mock(return_value=self.valid_config)

        # Actual call
        self.pod_collection._change_pod_config(
            self.test_pod,
            {'node': self.node},
        )

        get_pod_config_mock.assert_called_once_with(self.test_pod.id)
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


class TestExtractSecrets(unittest.TestCase):
    def test_extract_secrets(self):
        secrets = [
            ('wncm', 'pwd-1', Image('wncm/my-image').full_registry),
            ('wncm-2', 'pwd-2', Image('45.55.52.203:5/img-3').full_registry),
        ]
        containers = [
            {'image': 'nginx'},
            {'image': 'wncm/my-img',
             'secret': {'username': secrets[0][0], 'password': secrets[0][1]}},
            {'image': 'wncm/my-img-2',
             'secret': {'username': secrets[0][0], 'password': secrets[0][1]}},
            {'image': '45.55.52.203:5/img-3',
             'secret': {'username': secrets[1][0], 'password': secrets[1][1],
                        'registry': secrets[1][2]}},
        ]
        result = podcollection.extract_secrets(containers)
        self.assertEqual(result, set(secrets))
        for container in containers:
            self.assertNotIn('secrets', container)


class TestFixRelativeMountPaths(unittest.TestCase):
    def test_fix_relative_mount_paths(self):
        containers = [
            {},  # no volumeMounts
            {'volumeMounts': [{'name': 'vm-1', 'mountPath': '/data-1'},
                              {'name': 'vm-2', 'mountPath': './data-2'},
                              {'name': 'vm-3', 'mountPath': 'data-3'}]},
        ]
        fixed_containers = [
            {},
            {'volumeMounts': [{'name': 'vm-1', 'mountPath': '/data-1'},
                              {'name': 'vm-2', 'mountPath': '/data-2'},
                              {'name': 'vm-3', 'mountPath': '/data-3'}]},
        ]
        podcollection.fix_relative_mount_paths(containers)
        self.assertEqual(containers, fixed_containers)


class TestPodCollectionEdit(DBTestCase, TestCaseMixin):
    def setUp(self):
        self.secret_name = 'a2e43147-5bfe-4b50-9d0b-891a3acb95b2'
        self.old_secret = ('username-1', 'password-1',
                           Image('wncm/my-img').full_registry)
        self.new_secret = ('username-2', 'password-2',
                           Image('45.55.52.203:5000/my-img').full_registry)
        self.all_secrets = [self.old_secret, self.new_secret]

        self.mock_methods(
            podcollection.PodCollection, '_get_namespaces', '_get_pods',
            '_merge', 'get_secrets', '_save_k8s_secrets')

        self.user, _ = self.fixtures.user_fixtures()
        self.db_pod = self.fixtures.pod(owner=self.user, kube_id=0, config={
            'containers': [{'name': 'wj5cw1y4', 'image': 'wncm/my-img',
                            'kubes': 1}],
            'namespace': 'a99e70fe-f2e9-42dd-8e2b-94d277553250',
            'restartPolicy': 'Always',
            'secrets': [self.secret_name],
            'sid': 'fdcb7959-9a0d-4969-bd55-a3f5fdcb3fa8',
            'volumes': [],
            'volumes_public': [],
        })
        self.edited = {
            'name': self.db_pod.name + 'qwerty',
            'restartPolicy': 'Never',
            'kube_type': 1,
            'containers': [{  # edited container
                'name': 'wj5cw1y4',
                'image': 'wncm/my-img',
                'secret': {'username': self.old_secret[0],
                           'password': self.old_secret[1]},
                'kubes': 2,
            }, {  # added container
                'name': 'woeufh29',
                'image': '45.55.52.203:5000/my-img',
                'secret': {'username': self.new_secret[0],
                           'password': self.new_secret[1]},
            }]
        }

        pc = podcollection.PodCollection
        pc._save_k8s_secrets.side_effect = lambda *a, **kw: [str(uuid4())]
        pc.get_secrets.return_value = {self.secret_name: self.old_secret}

        self.podcollection = podcollection.PodCollection(self.user)
        self.orig_pod = podcollection.Pod(dict(
            self.db_pod.get_dbconfig(), id=self.db_pod.id,
            name=self.db_pod.name, owner=self.db_pod.owner,
            kube_type=self.db_pod.kube_id))

    @mock.patch.object(podcollection.PodCollection, '_preprocess_new_pod')
    def test_edited_config_saved(self, _preprocess_new_pod):
        _preprocess_new_pod.return_value = (self.edited, self.all_secrets)
        self.podcollection.edit(self.orig_pod, {'edited_config': self.edited})
        self.assertIsNotNone(self.db_pod.get_dbconfig().get('edited_config'))

    @mock.patch.object(podcollection.PodCollection, '_preprocess_new_pod')
    def test_preprocess_new_pod_called(self, _preprocess_new_pod):
        _preprocess_new_pod.return_value = (self.edited, self.all_secrets)
        self.podcollection.edit(self.orig_pod, {'edited_config': self.edited})
        _preprocess_new_pod.assert_called_once_with(
            self.edited, original_pod=self.orig_pod, skip_check=False)

        _preprocess_new_pod.reset_mock()
        self.podcollection.edit(self.orig_pod,
                                {'edited_config': self.edited},
                                skip_check=True)
        _preprocess_new_pod.assert_called_once_with(
            self.edited, original_pod=self.orig_pod, skip_check=True)

    @mock.patch.object(podcollection.PodCollection, '_preprocess_new_pod')
    def test_create_only_new_secrets(self, _preprocess_new_pod):
        """PodCollection.edit shouldn't duplicate secrets."""
        prepared_config = copy.deepcopy(self.edited)
        for container in prepared_config['containers']:
            container.pop('secrets', None)
            container.setdefault('kubes', 1)
        _preprocess_new_pod.return_value = (prepared_config, self.all_secrets)

        self.podcollection.edit(self.orig_pod, {'edited_config': self.edited})
        self.podcollection._save_k8s_secrets.assert_called_once_with(
            set([self.new_secret]), self.orig_pod.namespace)

    @mock.patch.object(podcollection.Image, 'check_containers',
                       mock.Mock(return_value=None))
    @mock.patch.object(podcollection, 'update_service',
                       mock.Mock())
    def test_apply_edit(self):
        self.maxDiff = None
        edited = dict(self.edited,
                      namespace='024ab4aa-8457-478d-8d4a-5007d70a2ff9')
        config = dict(
            self.db_pod.get_dbconfig(), id=self.db_pod.id,
            name=self.db_pod.name, owner=self.db_pod.owner,
            kube_type=self.db_pod.kube_id, edited_config=edited,
            namespace='024ab4aa-8457-478d-8d4a-5007d70a2ff9'
        )

        orig_pod = podcollection.Pod(config)
        orig_pod.status = 'stopped'
        self.db_pod.set_dbconfig(config)
        self.podcollection._apply_edit(orig_pod, self.db_pod, config)
        new_config = self.db_pod.get_dbconfig()
        self.assertEqual(len(new_config['containers']), len(self.edited[
            'containers']))
        self.assertEqual(new_config['containers'][0]['kubes'],
                         self.edited['containers'][0]['kubes'])

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger('TestPodCollection.test_pod').setLevel(logging.DEBUG)
    unittest.main()
