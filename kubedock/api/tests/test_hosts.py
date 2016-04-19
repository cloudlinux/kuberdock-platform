import mock

from kubedock.testutils.testcases import APITestCase


class TestHosts(APITestCase):
    @mock.patch('kubedock.api.hosts.register_host')
    def test_get_admin_only(self, register_host):
        response = self.admin_open('/hosts/register', method='POST',
                                   environ_base={'REMOTE_ADDR': '1.2.3.4'})
        self.assert200(response)
        register_host.assert_called_once_with('1.2.3.4')
