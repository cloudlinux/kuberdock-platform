from collections import namedtuple
from datetime import datetime
import unittest
import subprocess
import nginx

import mock

from ..testutils.testcases import DBTestCase
from ..exceptions import APIError
from ..login import get_user_role

from ..utils import (
    atomic,
    get_api_url,
    compose_dnat,
    from_binunit,
    parse_datetime_str,
    update_dict,
    run_ssh_command,
    all_request_params,
    get_available_port,
    get_current_dnat,
    get_timezone,
    update_allowed,
    from_siunit,
    get_version,
)


class TestAtomic(DBTestCase):
    class TargetAPIEror(APIError):
        """Some APIError inside target code"""

    class CreatePackageError(APIError):
        """Common error that should be rised instead of any non-`APIError`"""
        status_code = 500
        message = "Couldn't create package."

    def setUp(self):
        from kubedock.billing.models import Package

        self.Package = Package

        self.total_before = len(self.Package.query.all())
        self.current_transaction = self.db.session.begin_nested()

        patcher = mock.patch('kubedock.utils.current_app')
        self.addCleanup(patcher.stop)
        self.app_logger = patcher.start().logger

    def _target_with_exception(self):
        self.db.session.begin_nested()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        self.db.session.commit()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        raise Exception('Exception inside target code')
        self.db.session.add(self.Package(name=self.fixtures.randstr()))

    def _target_with_APIError(self):
        self.db.session.begin_nested()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        self.db.session.commit()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        raise self.TargetAPIEror('APIError inside target code')
        self.db.session.add(self.Package(name=self.fixtures.randstr()))

    def _target_without_exception(self):
        self.db.session.add(self.Package(name=self.fixtures.randstr()))

        self.db.session.begin_nested()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        self.db.session.rollback()

        self.db.session.begin_nested()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        self.db.session.commit()

        self.db.session.add(self.Package(name=self.fixtures.randstr()))

    def _target_with_commit(self):
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        self.db.session.commit()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))

    def _target_with_rollback(self):
        self.db.session.add(self.Package(name=self.fixtures.randstr()))
        self.db.session.rollback()
        self.db.session.add(self.Package(name=self.fixtures.randstr()))

    def test_with_exception(self):
        """
        If some non-`APIError` was rised, rollback all changes,
        and raise `CreatePackageError` instead.
        """

        with self.assertRaises(self.CreatePackageError):
            with atomic(self.CreatePackageError()):
                self._target_with_exception()
        self.assertEqual(self.app_logger.warn.call_count, 1)

        # Nothing's changed
        self.assertEqual(self.total_before, len(self.Package.query.all()))
        # Current thansaction wasn't commited or rolled back
        self.assertTrue(self.current_transaction.is_active)

    def test_with_api_error(self):
        """If some `APIError` was rised, don't stop it, 
        but rollback all changes."""
        with self.assertRaises(self.TargetAPIEror):  # original exception
            with atomic(self.CreatePackageError()):
                self._target_with_APIError()

        # Nothing's changed
        self.assertEqual(self.total_before, len(self.Package.query.all()))
        # Current thansaction wasn't commited or rolled back
        self.assertTrue(self.current_transaction.is_active)

    def test_ok(self):
        """If everything is ok, preserve changes."""
        with atomic(self.CreatePackageError()):
            self._target_without_exception()

        # There are some changes
        self.assertEqual(self.total_before + 3, len(self.Package.query.all()))
        # But current thansaction wasn't commited or rolled back
        self.assertTrue(self.current_transaction.is_active)

    def test_ok_and_commit_current_transaction(self):
        """If everything is ok, 
        preserve changes and commit current transaction."""
        with atomic(self.CreatePackageError(), nested=False):
            self._target_without_exception()

        # There are some changes
        self.assertEqual(self.total_before + 3, len(self.Package.query.all()))
        # Current thansaction was commited
        self.assertFalse(self.current_transaction.is_active)

    def test_ok_as_decrator(self):
        """Test decorator form."""
        decorator = atomic(self.CreatePackageError())
        decorator(self._target_without_exception)()

        # There are some changes
        self.assertEqual(self.total_before + 3, len(self.Package.query.all()))
        # But current thansaction wasn't commited or rolled back
        self.assertTrue(self.current_transaction.is_active)

    def test_ok_and_commit_current_transaction_as_decrator(self):
        """
        Parameter `commit` in decorated function 
        must override parameter `nested`
        in `atomic` decorator.
        """
        decorator = atomic(self.CreatePackageError())
        decorator(self._target_without_exception)(commit=True)

        # There are some changes
        self.assertEqual(self.total_before + 3, len(self.Package.query.all()))
        # Current thansaction was commited
        self.assertFalse(self.current_transaction.is_active)

    def test_main_transaction_commited(self):
        """Prevent main transaction from beeng commited 
        inside of atomic block."""
        with self.assertRaises(atomic.UnexpectedCommit):
            with atomic():
                self._target_with_commit()
        # Nothing's changed
        self.assertEqual(self.total_before, len(self.Package.query.all()))
        # Current thansaction wasn't commited or rolled back
        self.assertTrue(self.current_transaction.is_active)

    def test_main_transaction_rolled_back(self):
        """
        Raise an exception if main transaction was rolled back
        inside of atomic block
        """
        with self.assertRaises(atomic.UnexpectedRollback):
            with atomic():
                self._target_with_rollback()
        # Nothing's changed
        self.assertEqual(self.total_before, len(self.Package.query.all()))
        # Current thansaction wasn't commited or rolled back
        self.assertTrue(self.current_transaction.is_active)

    def test_nested(self):
        """Test nested usage."""
        with self.assertRaises(self.TargetAPIEror):  # original exception
            with atomic(self.CreatePackageError()):
                with atomic(self.CreatePackageError()):
                    with atomic(self.CreatePackageError()):
                        self._target_without_exception()
                    self._target_with_APIError()
                self.assertEqual(self.app_logger.warn.call_count, 1)
                self._target_without_exception()

        # Nothing's changed
        self.assertEqual(self.total_before, len(self.Package.query.all()))
        # Current thansaction wasn't commited or rolled back
        self.assertTrue(self.current_transaction.is_active)


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

    def test_base_url_completely_overrides_base_in_a_default_api_url(self):
        expected = 'http://localhost:8080/apis/kuberdock.com/v1/namespaces' \
                   '/default'
        self.assertEqual(get_api_url(base_url='/apis/kuberdock.com'), expected)

    def test_base_url_override_works_with_api_version_param(self):
        expected = 'http://localhost:8080/apis/kuberdock.com/v2/namespaces' \
                   '/default'
        self.assertEqual(get_api_url(base_url='/apis/kuberdock.com',
                                     api_version='v2'), expected)

    def test_base_url_override_works_with_multiple_version_and_args(self):
        expected = 'http://localhost:8080/apis/kuberdock.com/v2/namespaces' \
                   '/default/freepublicipcounters/node1'
        self.assertEqual(get_api_url('freepublicipcounters', 'node1',
                                     base_url='/apis/kuberdock.com',
                                     api_version='v2'), expected)

# TODO: remove after handle_aws_node
class TestUtilsComposes(unittest.TestCase):

    def test_composes(self):
        self.assertEquals('iptables -t nat -A PREROUTING -i enp0s5 -p tcp '
                          '-d 192.168.168.168/32 --dport 8080 -j DNAT '
                          '--to-destination 10.254.10.10:54321',
                          compose_dnat('A', 'enp0s5', 'tcp',
                                       '192.168.168.168/32', 8080,
                                       '10.254.10.10', 54321))


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


class TestLoginGetUserRole(unittest.TestCase):
    @mock.patch('kubedock.login.logout_user')
    @mock.patch('kubedock.login.g')
    @mock.patch('kubedock.login.current_user')
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
        logout_user_mock.assert_called_once_with()


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


# TODO: remove after handle_aws_node
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


class TestUtilUpdateNginxProxyRestriction(unittest.TestCase):

    conf = """
            server {
                listen 8123;
                server_name localhost;

                location / {
                    return 403;
                }

                location /v2 {
                    return 403;
                }

                location /v2/keys {
                    proxy_pass http://127.0.0.1:4001;
                    allow bla-bla.com
                }
            }

            server {
                listen 8124;
                server_name localhost2;

                location / {
                    return 403;
                }

                location /v2/keys {
                    proxy_pass http://127.0.0.1:4001;
                    allow bla-bla.com
                }

                location /v2/values {
                    proxy_pass http://127.0.0.1:4002;
                    allow bla2-bla2.com
                }
            }
        """
    accept_ips = ['127.0.0.1', '192.168.3.1', '192.168.3.2']

    def test_update_allowed(self):

        def check_ips(location):
            ips = [key.value for key in location.keys if key.name == 'allow']
            self.assertEqual(self.accept_ips, ips)
            self.assertEqual(location.keys[-1].as_dict(), {'deny': 'all'})

        conf = nginx.loads(self.conf)
        update_allowed(self.accept_ips, conf)
        servers = conf.filter('Server')
        location = servers[0].filter('Location')[0]
        self.assertFalse(any([key.name in ('allow', 'deny')
                              for key in location.keys]))
        location = servers[0].filter('Location')[1]
        self.assertFalse(any([key.name in ('allow', 'deny')
                              for key in location.keys]))
        location = servers[0].filter('Location')[2]
        check_ips(location)
        location = servers[1].filter('Location')[0]
        self.assertFalse(any([key.name in ('allow', 'deny')
                              for key in location.keys]))
        location = servers[1].filter('Location')[1]
        check_ips(location)
        location = servers[1].filter('Location')[2]
        check_ips(location)


class TestUtilsFromSiunit(unittest.TestCase):

    def test_from_siunit(self):
        self.assertEquals(from_siunit('4'), 4.0)
        self.assertEquals(from_siunit('2200m'), 2.2)


class TestGetVersion(unittest.TestCase):

    @mock.patch('kubedock.utils.subprocess.check_output')
    def test_get_version_of_non_existent(self, _run):
        _run.side_effect = subprocess.CalledProcessError(1, 'command')
        expected = 'unknown'
        ver = get_version('kuberdoc')
        self.assertEqual(expected, ver,
                         "version extected to be {0} but {1} got".format(
                             expected, ver))
if __name__ == '__main__':
    unittest.main()
