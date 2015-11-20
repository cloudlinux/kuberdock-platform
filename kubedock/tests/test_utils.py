from collections import namedtuple
from datetime import datetime
import json
import unittest

import flask
import mock

from ..utils import (
    APIError,
    get_api_url,
    compose_dnat,
    compose_mark,
    compose_check,
    from_binunit,
    parse_datetime_str,
    update_dict,
    set_limit,
    run_ssh_command,
    all_request_params,
    get_user_role,
    get_available_port,
    get_current_dnat,
    handle_generic_node,
    set_bridge_rules,
    modify_node_ips,
    unbind_ip,
    get_timezone,
)


class TestUtilsGetApiUrl(unittest.TestCase):

    def test_expected_urls(self):
        self.assertEquals('http://localhost:8080/api/v1/pods',
                          get_api_url('pods', namespace=False))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/default/pods',
            get_api_url('pods'))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/default/pods',
            get_api_url('pods', namespace='default'))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/default/pods/some-pod',
            get_api_url('pods', 'some-pod'))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/zxc/pods/asd',
            get_api_url('pods', 'asd', namespace='zxc'))

        self.assertEquals('http://localhost:8080/api/v1/namespaces',
                          get_api_url('namespaces', namespace=False))

        self.assertEquals('http://localhost:8080/api/v1/namespaces/asd',
                          get_api_url('namespaces', 'asd', namespace=False))

        self.assertEquals('ws://localhost:8080/api/v1/endpoints?watch=true',
                          get_api_url('endpoints', namespace=False, watch=True))

        self.assertEquals(
            'ws://localhost:8080/api/v1/namespaces/test/endpoints?watch=true',
            get_api_url('endpoints', namespace='test', watch=True))

        self.assertEquals(
            'ws://localhost:8080/api/v1/namespaces/n/endpoints/t1?watch=true',
            get_api_url('endpoints', 't1', namespace='n', watch=True))

        # Special pod name
        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094/pods/unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
            get_api_url(
                'pods', 'unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
                namespace='user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094'))

        # Special ns name
        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/user-unnamed-1-v1cf712fd0bea4ac37ab9e12a2ee3094/pods/unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
            get_api_url(
                'pods', 'unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
                namespace='user-unnamed-1-v1cf712fd0bea4ac37ab9e12a2ee3094'))


class TestUtilsComposes(unittest.TestCase):

    def test_composes(self):
        self.assertEquals('iptables -t nat -A PREROUTING -i enp0s5 -p tcp '
                          '-d 192.168.168.168/32 --dport 8080 -j DNAT '
                          '--to-destination 10.254.10.10:54321',
                          compose_dnat('A', 'enp0s5', 'tcp',
                                       '192.168.168.168/32', 8080,
                                       '10.254.10.10', 54321))

        self.assertEquals('iptables -A FORWARD -i docker0 -o docker0 '
                          '-s 10.254.10.20/32 -j MARK --set-mark 0x4',
                          compose_mark('A', '10.254.10.20/32', '0x4'))

        self.assertEquals('iptables -A FORWARD -i docker0 -o docker0 '
                          '-d 10.254.10.20/32 -m mark ! --mark 0x4 '
                          '-j REJECT',
                          compose_check('A', '10.254.10.20/32', '0x4'))


class TestUtilsFromBinunit(unittest.TestCase):

    def test_from_binunit(self):
        self.assertEquals(from_binunit('1017368Ki'), 1041784832)
        self.assertEquals(from_binunit('1017368Ki', 'GiB', 2), 0.97)
        self.assertEquals(from_binunit('1017368Ki', 'GiB', 0), 1)
        self.assertEquals(from_binunit('1017368Ki', 'MiB'), 993.5234375)
        self.assertEquals(from_binunit('1017368Ki', 'MiB', 0), 994)
        self.assertEquals(from_binunit('1017368Ki', 'MiB', rtype=int), 993)
        self.assertEquals(from_binunit('1017368Ki', 'MiB', 0, float), 994.0)
        self.assertEquals(from_binunit('1017368Ki', 'MiB',
                                       rtype=lambda x: float(int(x))), 993.0)


class TestUtilsParseDatetimeStr(unittest.TestCase):

    def test_parse_datetime_str(self):
        dt = datetime(2000, 1, 20, 12, 34, 56)
        self.assertEquals(parse_datetime_str("2000-01-20"),
                          dt.replace(hour=0, minute=0, second=0))
        self.assertEquals(parse_datetime_str("2000-01-20 12:34:56"), dt)
        self.assertEquals(parse_datetime_str("2000-01-20T12:34:56"), dt)
        self.assertEquals(parse_datetime_str("2000-01-20T12:34:56Z"), dt)


class TestUtilsUpdateDict(unittest.TestCase):

    def test_update_dict(self):
        dict_in = {
            'foo': {
                'bar': 'baz',
                'hello': 'world'
            },
            'lorem': 'ipsum'
        }
        dict_diff = {
            'foo': {
                'hello': 'universe'
            }
        }
        dict_out = {
            'foo': {
                'bar': 'baz',
                'hello': 'universe'
            },
            'lorem': 'ipsum'
        }
        update_dict(dict_in, dict_diff)
        self.assertEquals(dict_in, dict_out)


class TestUtilsSetLimit(unittest.TestCase):

    @mock.patch('kubedock.utils.Pod')
    @mock.patch('kubedock.utils.Kube')
    @mock.patch('kubedock.utils.ssh_connect')
    def test_set_limit(self, ssh_connect_mock, kube_mock, pod_mock):
        host = 'node'
        pod_id = 'abcd'
        containers = {'first': 'lorem', 'second': 'ipsum'}
        app = flask.Flask(__name__)

        kube_mock.query.values.return_value = (1, 1, 'GB'),
        pod_cls = type('Pod', (), {
            'config': json.dumps({
                'containers': [
                    {'name': c, 'kubes': len(c)} for c in containers.keys()
                ],
                'kube_type': 1
            })
        })
        pod_mock.query.filter_by.return_value.first.return_value = pod_cls

        stdout = mock.Mock()
        stdout.channel.recv_exit_status.return_value = 1

        ssh = mock.Mock()
        ssh.exec_command.return_value = (mock.Mock(), stdout, mock.Mock())
        ssh_connect_mock.return_value = (ssh, 'ignore this message')

        res = set_limit(host, pod_id, containers, app)
        self.assertFalse(res)

        ssh_connect_mock.return_value = (ssh, None)
        res = set_limit(host, pod_id, containers, app)
        self.assertFalse(res)

        stdout.channel.recv_exit_status.return_value = 0
        res = set_limit(host, pod_id, containers, app)
        self.assertTrue(res)

        ssh.exec_command.assert_called_with(
            'python '
            '/var/lib/kuberdock/scripts/fslimit.py '
            'ipsum=6g lorem=5g'
        )
        self.assertEqual(ssh.exec_command.call_count, 2)

        ssh_connect_mock.assert_called_with(host)
        self.assertEqual(ssh_connect_mock.call_count, 3)


class TestUtilsRunSSHCommand(unittest.TestCase):

    @mock.patch('kubedock.utils.ssh_connect')
    def test_run_ssh_command(self, ssh_connect_mock):
        host = 'node'
        command = 'uname -n'

        stdout = mock.Mock()
        stdout.channel.recv_exit_status.return_value = 1
        stdout.read.return_value = 'foo'

        stderr = mock.Mock()
        stderr.read.return_value = 'bar'

        ssh = mock.Mock()
        ssh.exec_command.return_value = (mock.Mock(), stdout, stderr)
        ssh_connect_mock.return_value = (ssh, 'error')

        self.assertRaises(APIError, run_ssh_command, host, command)

        ssh_connect_mock.return_value = (ssh, None)
        res = run_ssh_command(host, command)
        self.assertEqual(res, (1, 'bar'))

        stdout.channel.recv_exit_status.return_value = 0
        res = run_ssh_command(host, command)
        self.assertEqual(res, (0, 'foo'))

        ssh.exec_command.assert_called_with(command)
        self.assertEqual(ssh.exec_command.call_count, 2)

        ssh_connect_mock.assert_called_with(host)
        self.assertEqual(ssh_connect_mock.call_count, 3)


class TestUtilsAllRequestParams(unittest.TestCase):

    @mock.patch('kubedock.utils.request')
    def test_all_request_params(self, request_mock):
        dict1 = {'foo1': 'bar1'}
        dict2 = {'foo2': 'bar2'}
        dict3 = {'foo3': 'bar3'}

        expected = {}
        expected.update(dict1)
        expected.update(dict2)
        expected.update(dict3)

        dict1_wtoken = dict1.copy()
        dict1_wtoken.update({'token': 'abcd'})

        request_mock.args.to_dict.return_value = dict1_wtoken
        request_mock.json = dict2
        request_mock.form.to_dict.return_value = dict3
        self.assertEqual(all_request_params(), expected)


class TestUtilsGetUserRole(unittest.TestCase):

    @mock.patch('kubedock.utils.logout_user')
    @mock.patch('kubedock.utils.g')
    @mock.patch('kubedock.utils.current_user')
    def test_get_user_role(self, current_user_mock, g_mock, logout_user_mock):
        role1 = 'Admin'
        role2 = 'User'
        role3 = 'AnonymousUser'

        current_user_mock.role.rolename = role1
        self.assertEqual(get_user_role(), role1)

        del current_user_mock.role
        g_mock.user.role.rolename = role2
        self.assertEqual(get_user_role(), role2)

        del g_mock.user.role
        self.assertEqual(get_user_role(), role3)
        logout_user_mock.assert_called_once


class TestUtilsGetAvailablePort(unittest.TestCase):

    @mock.patch('kubedock.utils.random')
    @mock.patch('kubedock.utils.socket')
    def test_get_available_port(self, socket_mock, random_mock):
        host = 'node'
        port = 44444

        sock = mock.Mock()
        sock.connect_ex.return_value = 1
        socket_mock.socket.return_value = sock

        random_mock.randint.return_value = port

        res = get_available_port(host)
        self.assertEqual(res, port)
        sock.connect_ex.assert_called_with((host, port))


class TestUtilsGetCurrentDNAT(unittest.TestCase):

    def test_get_current_dnat(self):
        rules = (
            'Chain PREROUTING (policy ACCEPT)\n'
            'target     prot opt source               destination\n'
            'DNAT       tcp  --  0.0.0.0/0            192.168.77.129       tcp dpt:80 to:10.254.97.4:80\n'
            'KUBE-PORTALS-CONTAINER  all  --  0.0.0.0/0            0.0.0.0/0            /* handle ClusterIPs; NOTE: this must be before the NodePort rules */\n'
            'KUBE-NODEPORT-CONTAINER  all  --  0.0.0.0/0            0.0.0.0/0            ADDRTYPE match dst-type LOCAL /* handle service NodePorts; NOTE: this must be the last rule in the chain */\n'
        )

        NetData = namedtuple('NetData', ['host_port', 'pod_ip', 'pod_port'])

        out = mock.Mock()
        out.read.return_value = rules
        conn = mock.Mock()
        conn.exec_command.return_value = None, out, None

        expected = [NetData(80, '10.254.97.4', 80)]
        res = get_current_dnat(conn)
        self.assertEqual(expected, res)


class TestUtilsHandleGenericNode(unittest.TestCase):

    def test_handle_generic_node(self):
        stdout = mock.Mock()

        ssh = mock.Mock()
        service = 'abcd'
        cmd = 'add'
        pod_ip = '10.254.10.10'
        pub_ip = '192.168.168.168/32'
        ports = [
            {
                'name': 'web-public',
                'targetPort': 8080,
                'port': 80,
            },
            {
                'name': 'internal',
                'targetPort': 8090
            },
            {
                'name': 'syslog-public',
                'targetPort': 514,
                'protocol': 'udp'
            }
        ]
        app = flask.Flask(__name__)

        ssh.exec_command.return_value = (mock.Mock(), stdout, mock.Mock())

        stdout.channel.recv_exit_status.return_value = 1
        res = handle_generic_node(ssh, service, cmd, pod_ip, pub_ip, ports, app)
        self.assertFalse(res)

        stdout.channel.recv_exit_status.return_value = 0
        res = handle_generic_node(ssh, service, cmd, pod_ip, pub_ip, ports, app)
        self.assertTrue(res)

        cmd = 'del'
        res = handle_generic_node(ssh, service, cmd, pod_ip, pub_ip, ports, app)
        self.assertTrue(res)

        calls = [
            mock.call('bash /var/lib/kuberdock/scripts/modify_ip.sh add 192.168.168.168/32 enp0s3'),
            mock.call('bash /var/lib/kuberdock/scripts/modify_ip.sh add 192.168.168.168/32 enp0s3'),
            mock.call('iptables -t nat -C PREROUTING -i enp0s3 -p tcp -d 192.168.168.168/32 --dport 80 -j DNAT --to-destination 10.254.10.10:8080'),
            mock.call('iptables -t nat -C PREROUTING -i enp0s3 -p udp -d 192.168.168.168/32 --dport 514 -j DNAT --to-destination 10.254.10.10:514'),
            mock.call('bash /var/lib/kuberdock/scripts/modify_ip.sh del 192.168.168.168/32 enp0s3'),
            mock.call('iptables -t nat -D PREROUTING -i enp0s3 -p tcp -d 192.168.168.168/32 --dport 80 -j DNAT --to-destination 10.254.10.10:8080'),
            mock.call('iptables -t nat -D PREROUTING -i enp0s3 -p udp -d 192.168.168.168/32 --dport 514 -j DNAT --to-destination 10.254.10.10:514')
        ]
        ssh.exec_command.assert_has_calls(calls)


class TestUtilsSetBridgeRules(unittest.TestCase):

    @mock.patch('kubedock.utils.get_pod_owner_id')
    def test_set_bridge_rules(self, get_pod_owner_id_mock):
        get_pod_owner_id_mock.return_value = '0x4'

        stdout = mock.Mock()

        ssh = mock.Mock()
        service = 'abcd'
        cmd = 'add'
        pod_ip = '10.254.10.20'
        app = flask.Flask(__name__)

        ssh.exec_command.return_value = (mock.Mock(), stdout, mock.Mock())

        stdout.channel.recv_exit_status.return_value = 1
        set_bridge_rules(ssh, service, cmd, pod_ip, app)

        stdout.channel.recv_exit_status.return_value = 0
        set_bridge_rules(ssh, service, cmd, pod_ip, app)

        cmd = 'del'
        set_bridge_rules(ssh, service, cmd, pod_ip, app)

        calls = [
            mock.call('iptables -C FORWARD -i docker0 -o docker0 -s 10.254.10.20 -j MARK --set-mark 0x4'),
            mock.call('iptables -I FORWARD -i docker0 -o docker0 -s 10.254.10.20 -j MARK --set-mark 0x4'),
            mock.call('iptables -C FORWARD -i docker0 -o docker0 -d 10.254.10.20 -m mark ! --mark 0x4 -j REJECT'),
            mock.call('iptables -I FORWARD -i docker0 -o docker0 -d 10.254.10.20 -m mark ! --mark 0x4 -j REJECT'),
            mock.call('iptables -C FORWARD -i docker0 -o docker0 -s 10.254.10.20 -j MARK --set-mark 0x4'),
            mock.call('iptables -C FORWARD -i docker0 -o docker0 -d 10.254.10.20 -m mark ! --mark 0x4 -j REJECT'),
            mock.call('iptables -D FORWARD -i docker0 -o docker0 -s 10.254.10.20 -j MARK --set-mark 0x4'),
            mock.call('iptables -D FORWARD -i docker0 -o docker0 -d 10.254.10.20 -m mark ! --mark 0x4 -j REJECT')
        ]

        ssh.exec_command.assert_has_calls(calls)


class TestUtilsModifyNodeIPs(unittest.TestCase):

    @mock.patch('kubedock.utils.set_bridge_rules')
    @mock.patch('kubedock.utils.handle_generic_node')
    @mock.patch('kubedock.utils.handle_aws_node')
    @mock.patch('kubedock.utils.AWS', False)  # TODO: Test with AWS == True
    @mock.patch('kubedock.utils.ssh_connect')
    def test_modify_node_ips(self, ssh_connect_mock, handle_aws_node_mock,
                             handle_generic_node_mock, set_bridge_rules_mock):
        service = 'abcd'
        host = 'node'
        cmd = 'add'
        pod_ip = '10.254.10.10'
        public_ip = '192.168.168.168/32'
        ports = [
            {
                'name': 'web-public',
                'targetPort': 8080,
                'port': 80,
            },
            {
                'name': 'internal',
                'targetPort': 8090
            },
            {
                'name': 'syslog-public',
                'targetPort': 514,
                'protocol': 'udp'
            }
        ]
        app = flask.Flask(__name__)

        ssh = mock.Mock()

        ssh_connect_mock.return_value = (ssh, 'error')
        res = modify_node_ips(service, host, cmd, pod_ip, public_ip, ports, app)
        self.assertFalse(res)

        ssh_connect_mock.return_value = (ssh, None)
        handle_generic_node_mock.return_value = 'foo'
        res = modify_node_ips(service, host, cmd, pod_ip, public_ip, ports, app)
        handle_aws_node_mock.assert_not_called
        handle_generic_node_mock.assert_called_once_with(
            ssh, service, cmd, pod_ip, public_ip, ports, app
        )
        set_bridge_rules_mock.assert_called_once_with(
            ssh, service, cmd, pod_ip, app
        )
        self.assertEqual(res, 'foo')


class TestUtilsUnbindIP(unittest.TestCase):

    @mock.patch('kubedock.utils.modify_node_ips')
    def test_unbind_ip(self, modify_node_ips_mock):
        service_name = 'abcd'
        host = 'node'
        pod_ip = '10.254.10.10'
        public_ip = '192.168.168.168/32'
        ports = mock.Mock()
        state = {
            'assigned-to': host,
            'assigned-pod-ip': pod_ip,
            'assigned-public-ip': public_ip
        }
        service = {'spec': {'ports': ports}}
        verbosity = 0
        app = flask.Flask(__name__)

        unbind_ip(service_name, state, service, verbosity, app)
        modify_node_ips_mock.assert_called_with(service_name, host, 'del',
                                                pod_ip, public_ip, ports, app)


class TestUtilsGetTimezone(unittest.TestCase):

    @mock.patch('os.path.realpath')
    @mock.patch('os.path.islink')
    def test_get_timezone(self, islink_mock, realpath_mock):
        islink_mock.return_value = True
        realpath_mock.return_value = '/usr/share/zoneinfo/Europe/Kiev'

        res = get_timezone()
        self.assertEqual(res, 'Europe/Kiev')

        realpath_mock.return_value = '/foo/bar'
        self.assertRaises(OSError, get_timezone)

        islink_mock.return_value = False
        self.assertRaises(OSError, get_timezone)

        res = get_timezone(default_tz='UTC')
        self.assertEqual(res, 'UTC')


if __name__ == '__main__':
    unittest.main()
