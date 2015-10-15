"""Unit tests for kapi.images
"""
import unittest
import mock
import json
from urllib import urlencode
from urlparse import urlparse

import responses

from ..images import (Image, complement_registry, get_url, APIError)
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
NGINX_IMAGE_INFO = {
    'config': NGINX_CONFIG,
    'id': 'ceab60537ad28d87709d49420853766d02e9f3d4c0f4e36899d020e774b514d7'}


class TestImages(DBTestCase):
    @mock.patch.object(Image, '_request_image_info', autospec=True)
    def test_get_container_config(self, request_config_mock):
        """Test for kapi.images.Image.get_container_config function."""
        request_config_mock.return_value = NGINX_IMAGE_INFO
        result = Image('nginx').get_container_config()
        request_config_mock.assert_called_once_with(Image('nginx'), None)
        self.assertEqual(result, Image('nginx')._prepare_response(NGINX_CONFIG))

        # check and clear cache
        cache = images.DockerfileCache.query.all()
        self.assertEqual(len(cache), 1)
        images.DockerfileCache.query.delete()

        request_config_mock.return_value = None
        with self.assertRaises(APIError):
            Image('nginx').get_container_config()

    @responses.activate
    def test_v1request_config(self):
        """Test for kapi.images.Image._v1_request_image_info function."""
        image_url = 'nginx'  # [registry/]repo[:tag]
        registry, _, repo, tag = Image(image_url)
        auth = ('user', 'password')
        image = NGINX_IMAGE_INFO['id']

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
            return (200, {}, json.dumps(NGINX_IMAGE_INFO))
        responses.add_callback(responses.GET, v1_image_config_url,
                               callback=v1_image_conf_callback)
        res = Image(image_url)._v1_request_image_info(auth)
        self.assertEqual(res, NGINX_IMAGE_INFO)
        self.assertEqual(len(responses.calls), 3)
        self.assertEqual(responses.calls[0].request.url, v1_index_url)
        self.assertEqual(responses.calls[1].request.url, v1_image_url)
        self.assertEqual(responses.calls[2].request.url, v1_image_config_url)

        responses.reset()
        def index_v1_callback_401(request):
            return (401, {}, '')

        responses.add_callback(responses.GET, v1_index_url,
                               callback=index_v1_callback_401)
        res = Image(image_url)._v1_request_image_info(auth)
        self.assertIsNone(res)
        with self.assertRaises(APIError) as err:
            Image(image_url)._v1_request_image_info(auth)
        self.assertEqual(err.exception.status_code, 429)

    @responses.activate
    def test_v2request_config(self):
        """Test for kapi.images.Image._v2_request_image_info function."""
        image_url = 'nginx'  # [registry/]repo[:tag]
        registry, _, repo, tag = Image(image_url)
        auth = ('user', 'password')

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
                            {'v1Compatibility': json.dumps(NGINX_IMAGE_INFO)}
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

        res = Image(image_url)._v2_request_image_info(auth)
        self.assertEqual(res, NGINX_IMAGE_INFO)
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

        res = Image(image_url)._v2_request_image_info(auth)
        self.assertIsNone(res)
        with self.assertRaises(APIError) as err:
            Image(image_url)._v2_request_image_info(auth)
        self.assertEqual(err.exception.status_code, 429)

    @mock.patch.object(Image, '_v1_request_image_info', autospec=True)
    @mock.patch.object(Image, '_v2_request_image_info', autospec=True)
    def test_request_image_info(self, v2_req_mock, v1_req_mock):
        v2_req_mock.return_value = {'a': 'b'}
        res = Image('nginx')._request_image_info()
        self.assertEqual(res, v2_req_mock.return_value)
        v2_req_mock.assert_called_once_with(Image('nginx'), None)
        self.assertFalse(v1_req_mock.called)

        v2_req_mock.return_value = None
        v1_req_mock.return_value = 23232
        res = Image('nginx')._request_image_info()
        v1_req_mock.assert_called_once_with(Image('nginx'), None)
        self.assertEqual(res, v1_req_mock.return_value)

    # @unittest.skip('')
    def test_parse_image_name(self):
        DEFAULT_REGISTRY_HOST = urlparse(DEFAULT_REGISTRY).netloc
        test_pairs = {
            'nginx': (DEFAULT_REGISTRY, DEFAULT_REGISTRY_HOST,
                      'library/nginx', 'latest'),
            'some_user/some_repo': (DEFAULT_REGISTRY, DEFAULT_REGISTRY_HOST,
                                    'some_user/some_repo', 'latest'),
            'some_user/some_repo:4': (DEFAULT_REGISTRY, DEFAULT_REGISTRY_HOST,
                                      'some_user/some_repo', '4'),
            'quay.io/some_user/some_repo:4': ('https://quay.io', 'quay.io',
                                              'some_user/some_repo', '4'),
            '45.55.52.203:5000/some_repo': ('https://45.55.52.203:5000',
                                            '45.55.52.203:5000', 'some_repo', 'latest'),
            '45.55.52.203:5000/some_repo:4': ('https://45.55.52.203:5000',
                                              '45.55.52.203:5000', 'some_repo', '4')
        }
        for image_name, result in test_pairs.iteritems():
            self.assertEqual(Image(image_name), result)

    # @unittest.skip('')
    def test_complement_registry(self):
        test_pairs = {'quay.io': 'https://quay.io',
                      'quay.io/': 'https://quay.io',
                      'http://quay.io': 'http://quay.io',
                      'http://quay.io/': 'http://quay.io',
                      'https://quay.io': 'https://quay.io',
                      'https://quay.io/': 'https://quay.io'}
        for data, result in test_pairs.iteritems():
            self.assertEqual(complement_registry(data), result)

    # @unittest.skip('')
    def test_get_url(self):
        test_pairs = {
            ('https://quay.io/', 'v1', 'aa', 'bb'): 'https://quay.io/v1/aa/bb'
        }
        for data, result in test_pairs.iteritems():
            self.assertEqual(get_url(*data), result)

    @mock.patch.object(Image, '_v1_request_image_info', autospec=True)
    @mock.patch.object(Image, '_v2_request_image_info', autospec=True)
    def test_check_images_availability(self, v2_mock, v1_mock):
        """Check kapi.images.Image.check_images_availability function"""
        v2_mock.return_value = None
        v1_mock.return_value = None

        with self.assertRaises(APIError):
            Image.check_images_availability(['nginx'])
        v1_mock.assert_called_once_with(Image('nginx'), None, True)
        v2_mock.assert_called_once_with(Image('nginx'), None, True)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = True
        Image.check_images_availability(['nginx'])
        self.assertTrue(v1_mock.called)
        self.assertFalse(v2_mock.called)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = None
        v2_mock.return_value = True
        Image.check_images_availability(['nginx'])
        self.assertTrue(v1_mock.called)
        self.assertTrue(v2_mock.called)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = None
        v2_mock.return_value = None
        with self.assertRaises(APIError):
            Image.check_images_availability(
                ['quay.io/quay/redis', 'u1/test_private'],
                [('uname1', 'pwd1', 'quay.io')]
            )
        image = Image('quay.io/quay/redis')
        v1_mock.assert_any_call(image, None, True)
        v1_mock.assert_any_call(image, ('uname1', 'pwd1'), True)
        v2_mock.assert_any_call(image, None, True)
        v2_mock.assert_any_call(image, ('uname1', 'pwd1'), True)

        v1_mock.reset_mock()
        v2_mock.reset_mock()
        v1_mock.return_value = True
        Image.check_images_availability(
            ['quay.io/quay/redis', 'u1/test_private'],
            [('uname1', 'pwd1', 'quay.io')]
        )
        v1_mock.assert_any_call(Image('quay.io/quay/redis'), None, True)
        v1_mock.assert_any_call(Image('u1/test_private'), None, True)

    @mock.patch.object(Image, '_request_image_info', autospec=True)
    def test_get_id(self, request_image_info_mock):
        """Check kapi.images.Image.get_id function"""
        request_image_info_mock.return_value = NGINX_IMAGE_INFO
        self.assertEqual(Image('nginx').get_id(), NGINX_IMAGE_INFO['id'])
        request_image_info_mock.assert_called_once_with(Image('nginx'), None)

        request_image_info_mock.reset_mock()
        request_image_info_mock.return_value = None
        result = Image('nginx').get_id([
            ('username1', 'password1', 'other.registry'),
            ('username2', 'password2', DEFAULT_REGISTRY),
            ('username3', 'password3', DEFAULT_REGISTRY)
        ])
        self.assertIsNone(result)
        request_image_info_mock.assert_has_calls([
            mock.call(Image('nginx'), ('username2', 'password2')),
            mock.call(Image('nginx'), ('username3', 'password3')),
            mock.call(Image('nginx'), None),
        ])

        request_image_info_mock.reset_mock()
        request_image_info_mock.return_value = NGINX_IMAGE_INFO
        result = Image('nginx').get_id([
            ('username1', 'password1', 'other.registry'),
            ('username2', 'password2', DEFAULT_REGISTRY),
            ('username3', 'password3', DEFAULT_REGISTRY)
        ])
        self.assertEqual(result, NGINX_IMAGE_INFO['id'])
        request_image_info_mock.assert_called_once_with(
            Image('nginx'), ('username2', 'password2'))


if __name__ == '__main__':
    unittest.main()
