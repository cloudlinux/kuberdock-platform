"""Unit tests for kapi.images
"""
import unittest
import mock
import json
from urllib import urlencode

import responses

from ..images import (get_container_config, check_images_availability,
                      complement_registry, parse_image_name, get_url, APIError)
from .. import images
from ...settings import DEFAULT_REGISTRY
from ...testutils.testcases import DBTestCase

TESTUNAME = 'wncm'
TESTPASSWORD = 'mfhhh94kw02z'


NGINX_CONFIG = {
    u'AttachStderr': False,
    u'AttachStdin': False,
    u'AttachStdout': False,
    u'Cmd': [u'nginx', u'-g', u'daemon off;'],
    u'Domainname': u'',
    u'Entrypoint': None,
    u'Env': [u'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    u'NGINX_VERSION=1.9.5-1~jessie'],
    u'ExposedPorts': {u'443/tcp': {}, u'80/tcp': {}},
    u'Hostname': u'7b840bf4fc5e',
    u'Image': u'd8a70839d9617b3104ac0e564137fd794fab7c71900f6347e99fba7f3fe71a30',
    u'Labels': {},
    u'MacAddress': u'',
    u'NetworkDisabled': False,
    u'OnBuild': [],
    u'OpenStdin': False,
    u'PublishService': u'',
    u'StdinOnce': False,
    u'Tty': False,
    u'User': u'',
    u'VolumeDriver': u'',
    u'Volumes': {u'/var/cache/nginx': {}},
    u'WorkingDir': u''
}

class TestImages(DBTestCase):

    @mock.patch.object(images, 'request_config')
    def test_get_container_config(self, request_config_mock):
        """Test for kapi.images.get_container_config function."""
        request_config_mock.return_value = NGINX_CONFIG
        result = get_container_config('nginx')
        request_config_mock.assert_called_once_with(
            'library/nginx', 'latest', None, DEFAULT_REGISTRY
        )
        self.assertEqual(
            result,
            images.prepare_response(NGINX_CONFIG, 'library/nginx', 'latest',
                DEFAULT_REGISTRY)
        )

        # check and clear cache
        cache = images.DockerfileCache.query.all()
        self.assertEqual(len(cache), 1)
        images.DockerfileCache.query.delete()

        request_config_mock.return_value = None
        with self.assertRaises(APIError):
            get_container_config('nginx')

    @responses.activate
    def test_v1request_config(self):
        """Test for kapi.images.try_v1_request_config function."""
        repo = 'nginx'
        tag = 'latest'
        auth = ('user', 'password')
        registry = DEFAULT_REGISTRY
        image =\
            u'ceab60537ad28d87709d49420853766d02e9f3d4c0f4e36899d020e774b514d7'

        # Dockerhub v1 authorization
        v1_index_url = images.DOCKERHUB_V1_INDEX.rstrip('/') +\
            '/v1/repositories/' + repo + '/images'
        token1 = 'signature=2751d8e9806f7622bd6c3cc2ccf6f8a98f3666f1,'\
                 'repository="library/nginx",access=read'

        def index_v1_callback(request):
            self.assertEqual(request.headers['x-docker-token'], 'true')
            headers = {'x-docker-token': token1}
            return (200, headers, '')

        responses.add_callback(responses.GET, v1_index_url,
                               callback=index_v1_callback)

        v1_image_url = registry.rstrip('/') + '/v1/repositories/' + repo +\
            '/tags/' + tag
        def v1_image_callback(request):
            self.assertEqual(
                request.headers['authorization'],
                'Token ' + token1
            )
            return (200, {}, u'"{}"'.format(image))
        responses.add_callback(responses.GET, v1_image_url,
                               callback=v1_image_callback)

        v1_image_config_url = registry.rstrip('/') + '/v1/images/' + image +\
            '/json'
        def v1_image_conf_callback(request):
            self.assertEqual(
                request.headers['authorization'],
                'Token ' + token1
            )
            return (200, {}, json.dumps({'config': NGINX_CONFIG}))
        responses.add_callback(responses.GET, v1_image_config_url,
                               callback=v1_image_conf_callback)
        res = images.try_v1_request_config(repo, tag, auth, registry)
        self.assertEqual(res, NGINX_CONFIG)
        self.assertEqual(len(responses.calls), 3)
        self.assertEqual(responses.calls[0].request.url, v1_index_url)
        self.assertEqual(responses.calls[1].request.url, v1_image_url)
        self.assertEqual(responses.calls[2].request.url, v1_image_config_url)

        responses.reset()
        def index_v1_callback_401(request):
            return (401, {}, '')

        responses.add_callback(responses.GET, v1_index_url,
                               callback=index_v1_callback_401)
        res = images.try_v1_request_config(repo, tag, auth, registry)
        self.assertIsNone(res)
        with self.assertRaises(APIError) as err:
            images.try_v1_request_config(repo, tag, auth, registry)
        self.assertEqual(err.exception.status_code, 429)

    @responses.activate
    def test_v2request_config(self):
        """Test for kapi.images.try_v1_request_config function."""
        repo = 'nginx'
        tag = 'latest'
        auth = ('user', 'password')
        registry = DEFAULT_REGISTRY

        # docker V2 authorization scheme:
        # 1. GET registry.domain.com/v2/library/nginx/manifests/latest
        #   response will be with 401 status and 'www-authenticate' field in
        #   header with content like
        #       'www-authenticate':
        #       'Bearer realm="https://auth.docker.io/token",
        #       service="registry.docker.io",
        #       scope="repository:nginx:pull"
        # 2. GET token via parameters in 'www-authenticate'
        #   GET https://auth.docker.io/token?scope=repository%3Anginx%3Apull&service=registry.docker.io
        #   with optional auth params
        #   response will contains json with 'token' field
        # 3. GET original url
        # (registry.domain.com/v2/library/nginx/manifests/latest) with header
        #  'Authorization': 'Bearer ' + token
        # Will return requested image manifest with 'history' field containing
        # list of items with 'v1Compatibility' field representing V1 API
        # compatible image description.
        v2_request_url = registry.rstrip('/') + '/v2/' + repo + '/manifests/' +\
            tag
        realm = 'https://auth.docker.io/token'
        token_params = {
            'scope': 'repository:nginx:pull',
            'service': 'registry.docker.io'
        }
        token = 'qwerty'
        def config_request_callback(request):
            if not request.headers.get('Authorization', '').startswith('Bearer '):
                headers = {
                    'www-authenticate': 'Bearer {}'.format(
                        ','.join('{}="{}"'.format(key, value) for key, value
                                 in dict(realm=realm, **token_params).items())
                    )
                }
                return (401, headers, '')
            self.assertEqual(request.headers['Authorization'],
                             'Bearer {}'.format(token))
            return (200, {},
                    json.dumps({
                        'history': [
                            {
                                'v1Compatibility': json.dumps({
                                    'config': NGINX_CONFIG
                                })
                            }
                        ]
                    })
            )
        responses.add_callback(responses.GET, v2_request_url,
                               callback=config_request_callback)

        def token_request_callback(request):
            return (200, {}, json.dumps({'token': token}))

        responses.add_callback(responses.GET,
            realm + '?' + urlencode(token_params),
            callback=token_request_callback,
            match_querystring=True)

        res = images.try_v2_request_config(repo, tag, auth, registry)
        self.assertEqual(res, NGINX_CONFIG)
        self.assertEqual(len(responses.calls), 3)
        self.assertEqual(responses.calls[0].request.url, v2_request_url)
        self.assertEqual(responses.calls[1].request.url,
                         realm + '?' + urlencode(token_params))
        self.assertEqual(responses.calls[2].request.url, v2_request_url)

        responses.reset()
        def config_request_callback_401(request):
            headers = {
                'www-authenticate': 'Bearer {}'.format(
                    ','.join('{}="{}"'.format(key, value) for key, value
                                in dict(realm=realm, **token_params).items())
                )
            }
            return (401, headers, '')
        responses.add_callback(responses.GET, v2_request_url,
                               callback=config_request_callback_401)

        def token_request_callback_401(request):
            return (401, {}, json.dumps({'token': token}))
        responses.add_callback(responses.GET,
            realm + '?' + urlencode(token_params),
            callback=token_request_callback_401,
            match_querystring=True)

        res = images.try_v2_request_config(repo, tag, auth, registry)
        self.assertIsNone(res)
        with self.assertRaises(APIError) as err:
            images.try_v2_request_config(repo, tag, auth, registry)
        self.assertEqual(err.exception.status_code, 429)


    @mock.patch.object(images, 'try_v1_request_config')
    @mock.patch.object(images, 'try_v2_request_config')
    def test_request_config(self, v2_req_mock, v1_req_mock):
        v2_req_mock.return_value = {'a': 'b'}
        res = images.request_config('nginx')
        self.assertEqual(res, v2_req_mock.return_value)
        v2_req_mock.assert_called_once_with('nginx', 'latest', None,
                                            DEFAULT_REGISTRY)
        v1_req_mock.assert_not_called()
        v2_req_mock.return_value = None
        v1_req_mock.return_value = 23232
        res = images.request_config('nginx')
        v1_req_mock.assert_called_once_with('nginx', 'latest', None,
                                            DEFAULT_REGISTRY)
        self.assertEqual(res, v1_req_mock.return_value)

    #@unittest.skip('')
    def test_parse_image_name(self):
        test_pairs = {
            'nginx': (DEFAULT_REGISTRY, 'library/nginx', 'latest'),
            TESTUNAME + '/test_private': (
                DEFAULT_REGISTRY, TESTUNAME + '/test_private', 'latest'),
            TESTUNAME + '/test_private:4': (
                DEFAULT_REGISTRY, TESTUNAME + '/test_private', '4'),
            'quay.io/sergey_gruntovsky/test_private:4':
                ('quay.io', 'sergey_gruntovsky/test_private', '4'),
            '45.55.52.203:5000/mynginx':
                ('45.55.52.203:5000', 'mynginx', 'latest'),
            '45.55.52.203:5000/mynginx:4':
                ('45.55.52.203:5000', 'mynginx', '4')
        }
        for image_name, result in test_pairs.iteritems():
            self.assertEqual(parse_image_name(image_name), result)

    #@unittest.skip('')
    def test_complement_registry(self):
        test_pairs = {'quay.io': 'https://quay.io',
                      'http://quay.io': 'http://quay.io',
                      'https://quay.io': 'https://quay.io'}
        for data, result in test_pairs.iteritems():
            self.assertEqual(complement_registry(data), result)

    #@unittest.skip('')
    def test_get_url(self):
        test_pairs = {
            ('https://quay.io/', 'v1', 'aa', 'bb'): 'https://quay.io/v1/aa/bb'
        }
        for data, result in test_pairs.iteritems():
            self.assertEqual(get_url(*data), result)

    @mock.patch.object(images, 'try_v1_request_config')
    @mock.patch.object(images, 'try_v2_request_config')
    def test_check_images_availability(self, v2_mock, v1_mock):
        """Check kapi.images.check_images_availability function"""
        v2_mock.return_value = None
        v1_mock.return_value = None

        with self.assertRaises(APIError):
            check_images_availability(['nginx'])
        v1_mock.assert_called_once_with(
            'library/nginx', 'latest', None, DEFAULT_REGISTRY, True)
        v2_mock.assert_called_once_with(
            'library/nginx', 'latest', None, DEFAULT_REGISTRY, True)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = True
        check_images_availability(['nginx'])
        self.assertTrue(v1_mock.called)
        self.assertFalse(v2_mock.called)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = None
        v2_mock.return_value = True
        check_images_availability(['nginx'])
        self.assertTrue(v1_mock.called)
        self.assertTrue(v2_mock.called)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = None
        v2_mock.return_value = None
        with self.assertRaises(APIError):
            check_images_availability(
                ['quay.io/quay/redis', 'u1/test_private'],
                [('uname1', 'pwd1', 'quay.io')]
            )
        v1_mock.assert_any_call(
            'quay/redis', 'latest', None, 'https://quay.io', True)
        v1_mock.assert_any_call(
            'quay/redis', 'latest', ('uname1', 'pwd1'), 'https://quay.io', True)
        v2_mock.assert_any_call(
            'quay/redis', 'latest', None, 'https://quay.io', True)
        v2_mock.assert_any_call(
            'quay/redis', 'latest', ('uname1', 'pwd1'), 'https://quay.io', True)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = True
        check_images_availability(
            ['quay.io/quay/redis', 'u1/test_private'],
            [('uname1', 'pwd1', 'quay.io')]
        )
        v1_mock.assert_any_call(
            'quay/redis', 'latest', None, 'https://quay.io', True)
        v1_mock.assert_any_call(
            'u1/test_private', 'latest', None, DEFAULT_REGISTRY, True)


if __name__ == '__main__':
    unittest.main()
