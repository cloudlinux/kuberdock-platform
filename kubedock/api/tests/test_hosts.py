import mock

from kubedock.testutils.testcases import APITestCase


class TestHosts(APITestCase):
    ip = '1.2.3.4'

    @mock.patch('kubedock.api.hosts.register_host')
    def test_get_admin_only(self, register_host):
        register_host.return_value = {'ip': self.ip}
        response = self.admin_open('/hosts/register', method='POST',
                                   environ_base={'REMOTE_ADDR': self.ip})
        self.assert200(response)
        register_host.assert_called_once_with(self.ip)
