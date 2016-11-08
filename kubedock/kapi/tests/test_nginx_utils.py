import unittest

import nginx
import mock

from kubedock.kapi.nginx_utils import update_allowed
from kubedock.settings import MASTER_IP


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

    @mock.patch('kubedock.kapi.nginx_utils.RegisteredHost')
    def test_update_allowed(self, registered_host_mock):
        registered_host_mock.query.values.return_value = []

        def check_ips(location):
            ips = [key.value for key in location.keys if key.name == 'allow']
            self.assertEqual(self.accept_ips, ips)
            self.assertEqual(location.keys[-1].as_dict, {'deny': 'all'})

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


if __name__ == '__main__':
    unittest.main()
