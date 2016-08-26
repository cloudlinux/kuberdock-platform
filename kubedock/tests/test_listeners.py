from copy import deepcopy
from collections import OrderedDict
import flask
import json
import unittest
import mock
import logging
import sys
import uuid

from .. import listeners
from ..settings import NODE_LOCAL_STORAGE_PREFIX
from ..testutils.testcases import DBTestCase


global_patchers = [
    mock.patch.object(listeners, 'current_app'),
]


def setUpModule():
    for patcher in global_patchers:
        patcher.start()


def tearDownModule():
    for patcher in global_patchers:
        patcher.stop()


@mock.patch('kubedock.flask_sqlalchemy_fix.SignallingSession', autospec=True)
@mock.patch('kubedock.listeners.ConnectionPool.get_connection')
@mock.patch('kubedock.listeners.tasks.check_if_node_down.delay')
@mock.patch('kubedock.listeners.get_node_state')
class TestNodeEventListeners(DBTestCase):
    """process_nodes_event routine tests."""

    _data = {
        u'object': {
            u'status': {},
            u'metadata': {u'name': u'node1'}},
        u'type': u'MODIFIED'}

    def test_event_has_first_node_down_status(self, _ns, _t, _r, _s):
        app = mock.MagicMock()
        redis = mock.MagicMock()
        redis.configure_mock(**{
            'get.return_value': '["Ready", "True"]',
            'exists.return_value': False})
        _r.return_value = redis
        _ns.return_value = '["Ready", "Unknown"]'
        listeners.process_nodes_event(self._data, app)
        self.assertTrue(_t.called, "On node state change delayed task is expected to be called")

    def test_event_has_non_first_node_down_status(self, _ns, _t, _r, _s):
        app = mock.MagicMock()
        redis = mock.MagicMock()
        redis.configure_mock(**{
            'get.return_value': '["Ready", "True"]',
            'exists.return_value': True})
        _r.return_value = redis
        _ns.return_value = '["Ready", "Unknown"]'
        listeners.process_nodes_event(self._data, app)
        self.assertFalse(_t.called, "On repeated node down events delayed task is not expected to be called")


@mock.patch('kubedock.listeners.PodCollection')
class TestPodEventK8s(DBTestCase):

    _node_name = 'node1.kuberdock.local'
    _node_id = 32323
    _local_storage = [{'hostPath': {'path': NODE_LOCAL_STORAGE_PREFIX}}]
    _pod_id = str(uuid.uuid4())
    _data = {
        'type': 'MODIFIED',
        'object': {
            'metadata': {
                'labels': {
                    'kuberdock-pod-uid': _pod_id
                }
            },
            'spec': {
                'nodeName': _node_name,
                'nodeSelector': {},
                'volumes': [{
                    'hostPath': {
                        'path': '/var/lib/docker/containers'
                    }
                }]
            }
        }
    }

    def test_pod_has_no_localstorage(self, podcollection_mock):
        data = deepcopy(self._data)
        app = mock.MagicMock()
        listeners.process_pods_event_k8s(data, app)
        self.assertFalse(podcollection_mock.update.called)

    def test_pod_already_pined(self, podcollection_mock):
        data = deepcopy(self._data)
        data['object']['spec']['nodeSelector']['kuberdock-node-hostname'] = self._node_name
        app = mock.MagicMock()
        listeners.process_pods_event_k8s(data, app)
        self.assertFalse(podcollection_mock.update.called)

    @mock.patch('kubedock.listeners.User')
    @mock.patch('kubedock.listeners.Pod')
    @mock.patch('kubedock.listeners.PersistentDisk.bind_to_node')
    @mock.patch('kubedock.listeners.Node.get_by_name')
    def test_pin_pod_to_node(self, get_node_mock, bind_to_node_mock, pod_mock,
                             user_mock, podcollection_mock):
        data = deepcopy(self._data)
        data['object']['spec']['volumes'] = self._local_storage
        app = mock.MagicMock()
        user_mock.return_value = "some user"

        def get_db_config(param):
            if param == 'node':
                return None
            if param == 'volumes':
                data = deepcopy(self._local_storage)
                data[0]['annotation'] = {'localStorage': {}}
                return data

        pod_mock.query.filter_by.return_value.first.return_value.get_dbconfig\
            .side_effect = get_db_config
        node = type('Node', (), {
            'id': self._node_id,
            'hostname': self._node_name
        })
        get_node_mock.return_value = node
        pod_mock.query.filter_by.return_value.first.return_value.id = self._pod_id
        listeners.process_pods_event_k8s(data, app)
        self.assertTrue(pod_mock.query.filter_by.called)
        self.assertTrue(pod_mock.query.filter_by.return_value.first.called)
        self.assertTrue(podcollection_mock.return_value.update.called)
        bind_to_node_mock.assert_called_once_with(self._pod_id, self._node_id)
        get_node_mock.assert_called_once_with(self._node_name)


class TestSetLimit(unittest.TestCase):
    @mock.patch('kubedock.listeners.Pod')
    @mock.patch('kubedock.listeners.Kube')
    @mock.patch('kubedock.listeners.ssh_connect')
    def test_set_limit(self, ssh_connect_mock, kube_mock, pod_mock):
        host = 'node'
        pod_id = 'abcd'
        containers = OrderedDict([('second', 'ipsum'), ('first', 'lorem')])
        app = flask.Flask(__name__)

        kube_mock.query.values.return_value = (1, 1, 'GB'),
        pod_cls = type('Pod', (), {
            'kube_id': 1,
            'config': json.dumps({
                'containers': [
                    {'name': c, 'kubes': len(c)} for c in containers.keys()
                ],
            })
        })
        pod_mock.query.filter_by.return_value.first.return_value = pod_cls

        stdout = mock.Mock()
        stdout.channel.recv_exit_status.return_value = 1

        ssh = mock.Mock()
        ssh.exec_command.return_value = (mock.Mock(), stdout, mock.Mock())
        ssh_connect_mock.return_value = (ssh, 'ignore this message')

        res = listeners.set_limit(host, pod_id, containers, app)
        self.assertFalse(res)

        ssh_connect_mock.return_value = (ssh, None)
        res = listeners.set_limit(host, pod_id, containers, app)
        self.assertFalse(res)

        stdout.channel.recv_exit_status.return_value = 0
        res = listeners.set_limit(host, pod_id, containers, app)
        self.assertTrue(res)

        ssh.exec_command.assert_called_with(
            'python '
            '/var/lib/kuberdock/scripts/fslimit.py containers '
            'ipsum=6g lorem=5g'
        )
        self.assertEqual(ssh.exec_command.call_count, 2)

        ssh_connect_mock.assert_called_with(host)
        self.assertEqual(ssh_connect_mock.call_count, 3)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    unittest.main()
