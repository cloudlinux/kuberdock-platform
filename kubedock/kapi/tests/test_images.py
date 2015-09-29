import unittest
import mock
import sys

sys.modules['kubedock.core'] = mock.Mock()
sys.modules['kubedock.rbac.models'] = mock.Mock()
sys.modules['kubedock.users.models'] = mock.Mock()
sys.modules['kubedock.pods.models'] = mock.Mock()
sys.modules['kubedock.pods.models'].DockerfileCache.query.get.return_value = None
sys.modules['kubedock.utils'] = mock.Mock()
sys.modules['kubedock.utils'].APIError = type('APIError', (Exception,), {})

from ..images import get_container_config
from ...validation import (V, args_list_schema, env_schema, path_schema,
                           port_schema, protocol_schema)

schema = {
    'args': dict(args_list_schema, required=True),
    'command': dict(args_list_schema, required=True),
    'env': dict(env_schema, required=True),
    'image': {'type': str, 'required': True, 'empty': False},
    'ports': {'type': list, 'required': True, 'schema': {'type': dict, 'schema': {
        'number': dict(port_schema, required=True), 'protocol': protocol_schema}}},
    'volumeMounts': {'type': list, 'required': True, 'schema': {'type': str}},
    'workingDir': path_schema,
}


class TestImages(unittest.TestCase):
    def validate(self, data):
        validator = V()
        if not validator.validate(data, schema):
            self.fail(validator.errors)

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_public(self):
        self.validate(get_container_config('sergey_gruntovsky/mynginx',
                                           registry='quay.io'))

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_public_auth(self):
        self.validate(get_container_config(
            'sergey_gruntovsky/mynginx', registry='quay.io',
            auth=('sergey_gruntovsky+kdmynginx',
                  'QH2XTHF2G3320EAD16A9WC1EV50X3UE3IP9PSFWK28JVW8OYQFI37J3AVV3KE3AZ')
        ))

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_private(self):
        self.validate(get_container_config(
            'sergey_gruntovsky/test_private', registry='quay.io',
            auth=('sergey_gruntovsky+kd_test_private',
                  'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY')
        ))

    # @unittest.skip('')
    def test_get_container_config_public_official(self):
        self.validate(get_container_config('nginx'))
        self.validate(get_container_config('nginx', '1.9'))
        self.validate(get_container_config('debian'))

    # @unittest.skip('')
    def test_get_container_config_public(self):
        self.validate(get_container_config('wncm/mynginx4'))

    # @unittest.skip('')
    def test_get_container_config_private_dockerhub_repo(self):
        self.validate(get_container_config('wncm/test_private',
                                           auth=('wncm', 'mfhhh94kw02z')))
        self.validate(get_container_config('wncm/test_private', 'latest',
                                           auth={'username': 'wncm',
                                                 'password': 'mfhhh94kw02z'}))

    # @unittest.skip('')
    def test_get_container_config_private_registry(self):
        self.validate(get_container_config('mynginx', auth=('wncm', 'p-0'),
                                           registry='https://45.55.52.203:5000'))


if __name__ == '__main__':
    unittest.main()
