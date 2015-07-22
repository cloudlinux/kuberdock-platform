import logging
import mock
import sys
import unittest

from uuid import uuid4

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

from ..podcollection import PodCollection, ModelQuery, KUBERDOCK_INTERNAL_USER

class TestPodCollectionDelete(unittest.TestCase):

    def setUp(self):
        U = type('User', (), {'username': 'bliss'})
        PodCollection._get_namespaces = (lambda s: None)
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


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger('TestPodCollection.test_pod').setLevel(logging.DEBUG)
    unittest.main()