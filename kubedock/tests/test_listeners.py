import unittest
import mock
import logging
import sys

from .. import listeners


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
class TestNodeEventListeners(unittest.TestCase):
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
            'get.return_value':'["Ready", "True"]',
            'exists.return_value': False})
        _r.return_value = redis
        _ns.return_value = '["Ready", "Unknown"]'
        listeners.process_nodes_event(self._data, app)
        self.assertTrue(_t.called, "On node state change delayed task is expected to be called")


    def test_event_has_non_first_node_down_status(self, _ns, _t, _r, _s):
        app = mock.MagicMock()
        redis = mock.MagicMock()
        redis.configure_mock(**{
            'get.return_value':'["Ready", "True"]',
            'exists.return_value': True})
        _r.return_value = redis
        _ns.return_value = '["Ready", "Unknown"]'
        listeners.process_nodes_event(self._data, app)
        self.assertFalse(_t.called, "On repeated node down events delayed task is not expected to be called")

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    unittest.main()
