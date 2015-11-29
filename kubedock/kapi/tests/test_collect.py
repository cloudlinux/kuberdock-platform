import unittest
import mock
import copy
import subprocess

from .. import collect


class TestStatItem(unittest.TestCase):
    # TODO: add tests for send, collect
    _NODES_DATA = ['192.168.168.2', '192.168.168.3']

    _CADVISOR_REPLY = {
        u'filesystems': [
            {u'device': u'/dev/vda1', u'capacity': 10433613824},
            {u'device': u'/dev/vdb', u'capacity': 53660876800}],
        u'num_cores': 4,
        u'network_devices': [{u'mtu': 1500, u'name': u'eth0'}],
        u'memory_capacity': 1929428992,
        u'cpu_frequency_khz': 3392292}

    _EXTENDED_NODE_DATA = {'disks': [
            {u'device': u'/dev/vda1', u'capacity': 10433613824},
            {u'device': u'/dev/vdb', u'capacity': 53660876800}],
            'cores': 4, 'clock': 3392292, 'nics': 1, 'memory': 1929428992}

    _USERS_DATA = [{'username': 'kuberdock-internal', 'rolename': 'User'},
                   {'username': 'admin', 'rolename': 'Admin'},
                   {'username': 'valid', 'rolename': 'User'}]

    @mock.patch('kubedock.kapi.collect.Node')
    def test_fetch_nodes(self, _Node):
        _Node.get_all = mock.MagicMock(return_value=[type('_', (), {'ip': n})()
            for n in self._NODES_DATA])
        nodes = collect.fetch_nodes()
        self.assertTrue(_Node.get_all.called)
        self.assertEqual(nodes, [{'_ip': n} for n in self._NODES_DATA])

    @mock.patch('kubedock.kapi.collect.requests')
    def test_extend_nodes(self, _req):
        rv = mock.MagicMock(status_code=200,
            **{'json.return_value':copy.deepcopy(self._CADVISOR_REPLY)})
        _req.get = mock.MagicMock(return_value=rv)
        fmt = 'http://{0}:4194/api/v1.3/machine'
        expected = [mock.call(fmt.format(n)) for n in self._NODES_DATA]
        received = [copy.deepcopy(self._EXTENDED_NODE_DATA)
                        for i in range(len(self._NODES_DATA))]

        nodes = collect.extend_nodes([{'_ip': n} for n in self._NODES_DATA])
        self.assertEqual(_req.get.call_args_list, expected,
                         "requests get params differ from expected ones")
        self.assertEqual(nodes, received, "Extended data differ from expected")

    @mock.patch('kubedock.kapi.collect.UserCollection')
    def test_get_users(self, _users):
        _users().get.return_value = self._USERS_DATA
        users = collect.get_users_number()
        self.assertEqual(users, 1,
            "Users number must be 1 whereas now it is {0}".format(users))

    @mock.patch('kubedock.kapi.collect.Updates')
    def test_get_updates(self, _Upd):
        _Upd.query.all = mock.MagicMock(return_value=[type('_', (),
            {'fname': '00000_update.py', 'status': 'applied'})()])
        expected = [{'00000_update.py': 'applied'}]
        upd = collect.get_updates()
        self.assertEqual(upd, expected,
            "updates are {0} but {1} expected".format(str(upd), str(expected)))

    @mock.patch('kubedock.kapi.collect.PodCollection')
    def test_get_pods(self, _PodCollection):
        mock_inst = mock.MagicMock(
            **{'get.return_value': [
                {'status': 'stopped'},
                {'status': 'running'}]})
        _PodCollection.return_value = mock_inst
        expected = {'total': 2, 'running': 1}
        pods = collect.get_pods()
        mock_inst.get.assert_called_once_with(False)
        self.assertEqual(pods, expected,
            "Pods are expected to be {0} but got {1}".format(str(pods), str(expected)))

    @mock.patch('kubedock.kapi.collect.subprocess.check_output')
    def test_get_version(self, _run):
        _run.return_value = 'kuberdock-0.1.2.3.test.rpm'
        expected = '0.1.2.3'
        ver = collect.get_version('kuberdock')
        self.assertEqual(expected, ver,
            "version extected to be {0} but {1} got".format(expected, ver))

    @mock.patch('kubedock.kapi.collect.subprocess.check_output')
    def test_get_version_of_non_existent(self, _run):
        _run.side_effect = subprocess.CalledProcessError(1, 'command')
        expected = 'unknown'
        ver = collect.get_version('kuberdoc')
        self.assertEqual(expected, ver,
            "version extected to be {0} but {1} got".format(expected, ver))

    @mock.patch('kubedock.kapi.collect.subprocess.check_output')
    def test_get_version_of_unknown_format(self, _run):
        _run.side_effect = AttributeError('test exception')
        expected = 'unknown'
        ver = collect.get_version('kuberdoc')
        self.assertEqual(expected, ver,
            "version extected to be {0} but {1} got".format(expected, ver))

    @mock.patch('kubedock.kapi.collect.open', create=True)
    def test_read_id(self, _open):
        _open.return_value = mock.MagicMock(spec=file)
        fh = _open.return_value.__enter__.return_value
        expected = '0000'
        fh.read.return_value = '0000'
        rv = collect.read_or_write_id()
        fh.read.assert_called_once_with()
        self.assertEqual(rv, expected,
                         "Got {0} while expected {1}".format(rv, expected))

    @mock.patch('kubedock.kapi.collect.open', create=True)
    def test_write_id(self, _open):
        _open.return_value = mock.MagicMock(spec=file)
        fh = _open.return_value.__enter__.return_value
        expected = '0000'
        collect.read_or_write_id(expected)
        fh.write.assert_called_once_with(expected)

    @mock.patch('kubedock.kapi.collect.subprocess.check_output')
    @mock.patch('kubedock.kapi.collect.read_or_write_id')
    def test_get_installation_id(self, _RoW, _run):
        expected = '0000'
        _RoW.return_value = expected
        rv = collect.get_installation_id()
        _RoW.assert_called_once_with()
        self.assertFalse(_run.called)
        self.assertEqual(rv, expected,
            "Returned {0} while expected {1}".format(rv, expected))

    @mock.patch('kubedock.kapi.collect.subprocess.check_output')
    @mock.patch('kubedock.kapi.collect.read_or_write_id')
    def test_get_installation_id_non_existent(self, _RoW, _run):
        expected = '0000'
        _run.return_value = expected
        _RoW.return_value = None
        rv = collect.get_installation_id()
        self.assertEqual(_RoW.call_args_list, [mock.call(), mock.call(expected)],
            "read_or_write is expected to be called twice")
        self.assertEqual(rv, expected,
            "get_installation_id is expected to return {0} but got {0}".format(
                expected, rv))
        self.assertEqual(_run.call_args_list, [mock.call(['dbus-uuidgen', '--get'])],
            "subprocess.check_output is expected to be called once with certain params")


if __name__ == '__main__':
    unittest.main()
