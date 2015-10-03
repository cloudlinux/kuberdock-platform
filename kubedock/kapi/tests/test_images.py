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

from ..images import (get_container_config, check_images_availability,
                      complement_registry, parse_image_name, get_url, APIError)
from ...settings import DEFAULT_REGISTRY
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


class TestGetContainerConfig(unittest.TestCase):
    def validate(self, data):
        validator = V()
        if not validator.validate(data, schema):
            self.fail(validator.errors)

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_public(self):
        self.validate(get_container_config('quay.io/sergey_gruntovsky/mynginx'))

        self.validate(get_container_config('gcr.io/google_containers/etcd:2.0.9'))
        self.validate(get_container_config('gcr.io/google_containers/kube2sky:1.11'))
        self.validate(get_container_config(
            'gcr.io/google_containers/skydns:2015-03-11-001'))

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_public_auth(self):
        self.validate(get_container_config(
            'quay.io/sergey_gruntovsky/mynginx',
            auth=('sergey_gruntovsky+kdmynginx',
                  'QH2XTHF2G3320EAD16A9WC1EV50X3UE3IP9PSFWK28JVW8OYQFI37J3AVV3KE3AZ')
        ))

    # @unittest.skip('')
    def test_get_container_config_3rd_party_registry_private(self):
        self.validate(get_container_config(
            'quay.io/sergey_gruntovsky/test_private',
            auth=('sergey_gruntovsky+kd_test_private',
                  'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY')
        ))

    # @unittest.skip('')
    def test_get_container_config_public_official(self):
        self.validate(get_container_config('nginx'))
        self.validate(get_container_config('nginx:1.9'))
        self.validate(get_container_config('debian'))

    # @unittest.skip('')
    def test_get_container_config_public(self):
        self.validate(get_container_config('wncm/mynginx4'))

    # @unittest.skip('')
    def test_get_container_config_private_dockerhub_repo(self):
        self.validate(get_container_config('wncm/test_private',
                                           auth=('wncm', 'mfhhh94kw02z')))
        self.validate(get_container_config('wncm/test_private:latest',
                                           auth={'username': 'wncm',
                                                 'password': 'mfhhh94kw02z'}))

    # @unittest.skip('')
    def test_get_container_config_private_registry(self):
        self.validate(get_container_config('45.55.52.203:5000/mynginx',
                                           auth=('wncm', 'p-0')))


class TestMisc(unittest.TestCase):
    def test_parse_image_name(self):
        test_pairs = {
            'nginx': (DEFAULT_REGISTRY, 'library/nginx', 'latest'),
            'wncm/test_private': (DEFAULT_REGISTRY, 'wncm/test_private', 'latest'),
            'wncm/test_private:4': (DEFAULT_REGISTRY, 'wncm/test_private', '4'),
            'quay.io/sergey_gruntovsky/test_private:4':
                ('quay.io', 'sergey_gruntovsky/test_private', '4'),
            '45.55.52.203:5000/mynginx':
                ('45.55.52.203:5000', 'mynginx', 'latest'),
            '45.55.52.203:5000/mynginx:4':
                ('45.55.52.203:5000', 'mynginx', '4')
        }
        for image_name, result in test_pairs.iteritems():
            self.assertEqual(parse_image_name(image_name), result)

    def test_complement_registry(self):
        test_pairs = {'quay.io': 'https://quay.io',
                      'http://quay.io': 'http://quay.io',
                      'https://quay.io': 'https://quay.io'}
        for data, result in test_pairs.iteritems():
            self.assertEqual(complement_registry(data), result)

    def test_get_url(self):
        test_pairs = {('https://quay.io/', 'v1', 'aa', 'bb'): 'https://quay.io/v1/aa/bb'}
        for data, result in test_pairs.iteritems():
            self.assertEqual(get_url(*data), result)


# @unittest.skip('')
class TestCheckImagesAvailability(unittest.TestCase):
    def test_default_registry_public(self):
        check_images_availability(['nginx'])

    @unittest.skip('TODO: dockerhub too many failed login attempts')
    def test_default_registry_private(self):
        check_images_availability(['nginx', 'wncm/test_private'], [
            {'username': 'wncm', 'password': 'mfhhh94kw02z'}
        ])
        with self.assertRaises(APIError):
            check_images_availability(['nginx', 'wncm/test_private'], [
                {'username': 'wncm', 'password': 'wrong_password'}
            ])

    def test_gcr(self):
        check_images_availability(['gcr.io/google_containers/etcd:2.0.9',
                                   'gcr.io/google_containers/kube2sky:1.11',
                                   'gcr.io/google_containers/skydns:2015-03-11-001'])

    def test_quay(self):
        check_images_availability(['quay.io/quay/redis'])
        check_images_availability(
            ['quay.io/quay/redis', 'quay.io/sergey_gruntovsky/test_private'],
            [{'registry': 'quay.io',
              'username': 'sergey_gruntovsky+kd_test_private',
              'password': 'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY'}]
        )

        with self.assertRaises(APIError):
            check_images_availability(
                ['quay.io/quay/redis', 'quay.io/sergey_gruntovsky/test_private'],
                [{'username': 'sergey_gruntovsky+kd_test_private',
                  'password': 'IKTNTXDZPRG4YCVZ4N9RMRDHVK81SGRC56Z4J0T5C6IGXU5FTMVKDYTYAM0Y1GGY'}]
            )

        with self.assertRaises(APIError):
            check_images_availability(
                ['quay.io/quay/redis', 'quay.io/sergey_gruntovsky/test_private'],
                [{'registry': 'quay.io',
                  'username': 'sergey_gruntovsky+kd_test_private',
                  'password': 'wrong_password'}]
            )
        with self.assertRaises(APIError):
            check_images_availability(['quay.io/quay/redis',
                                       'quay.io/sergey_gruntovsky/test_private'])


if __name__ == '__main__':
    unittest.main()
