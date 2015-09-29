# -*- coding: utf-8 -*-
import json
import re
import requests
from urlparse import urlparse, parse_qsl
from collections import Mapping
from datetime import datetime, timedelta
from urllib import urlencode

from ..core import db
from ..pods.models import DockerfileCache
from ..utils import APIError
from ..settings import DEFAULT_REGISTRY


class DockerAuth(requests.auth.AuthBase):
    """Docker Registry v2 authentication + HTTP Basic Auth for private registry."""
    _bearer_pat = re.compile(r'bearer ', flags=re.IGNORECASE)

    def __init__(self, username=None, password=None):
        """
        Usage:
        DockerAuth('my-username', 'my-password')
        DockerAuth(username='my-username', password='my-password')
        DockerAuth(['my-username', 'my-password'])
        DockerAuth(), DockerAuth(None), DockerAuth(None, None)  # without credentials
        """
        if hasattr(username, '__iter__') and password is None:  # got one iterable
            username, password = username
        self.username, self.password = username, password
        self.num_401_calls = 0

    def get_token(self, chal):
        url = urlparse(chal.pop('realm'))
        query = urlencode(dict(parse_qsl(url.query), **chal))
        url = url._replace(query=query).geturl()
        auth = None if self.username is None else (self.username, self.password)
        return requests.get(url, auth=auth).json().get('token')

    def handle_401(self, response, **kwargs):
        s_auth = response.headers.get('www-authenticate')
        if not s_auth or self.num_401_calls > 0:
            return response
        self.num_401_calls += 1

        method = s_auth.split()[0].lower()
        if method in ('basic', 'bearer'):
            # Consume content and release the original connection
            # to allow our new request to reuse the same one.
            response.content
            response.raw.release_conn()
            prep = response.request.copy()

            if method == 'basic' and self.username is not None:  # private registry
                prep = requests.auth.HTTPBasicAuth(self.username, self.password)(prep)
            elif method == 'bearer':  # Docker Registry v2 authentication
                chal = requests.utils.parse_dict_header(
                    self._bearer_pat.sub('', s_auth, count=1))
                token = self.get_token(chal)
                if token is not None:
                    prep.headers['Authorization'] = 'Bearer {0}'.format(token)

            new_response = response.connection.send(prep, **kwargs)
            new_response.history.append(response)
            new_response.request = prep
            return new_response
        return response

    def __call__(self, request):
        request.register_hook('response', self.handle_401)
        return request


def get_url(base, *path):
    return urlparse(base)._replace(path='/'.join(path)).geturl()


def request_config(repo, tag='latest', auth=None, registry=DEFAULT_REGISTRY):
    """
    Get container config from image manifest using Docker Registry API v2 or
    from image/json using Docker Registry API v1.
    """
    s = requests.Session()
    s.verify = False  # FIXME: private registries with self-signed certs

    # try V2 API
    url = get_url(registry, 'v2', repo, 'manifests', tag)
    response = s.get(url, auth=DockerAuth(auth))
    if response.status_code == 200:
        return json.loads(response.json()['history'][0]['v1Compatibility'])['config']
    elif response.headers.get('docker-distribution-api-version') != 'registry/2.0':
        # try V1 API
        url = get_url(registry, 'v1/repositories', repo, 'tags', tag)
        response = s.get(url, auth=auth)  # get image id for the tag
        if response.status_code == 200:
            image_id = response.json()
            # get the right session cookie (otherwise "quay.io: namespace is missing" error)
            s.get(get_url(registry, 'v1/repositories', repo, 'images'), auth=auth)
            url = get_url(registry, 'v1/images', image_id, 'json')  # get image info
            response = s.get(url, auth=auth)
            if response.status_code == 200:
                return response.json()['config']


def prepare_response(raw_config, image, tag, registry=DEFAULT_REGISTRY):
    """Create api response using raw container config, image, tag and registry"""
    if not raw_config.get('Env'):
        raw_config['Env'] = []
    if not raw_config.get('ExposedPorts'):
        raw_config['ExposedPorts'] = []

    if registry != DEFAULT_REGISTRY:
        image = '{0}/{1}'.format(urlparse(registry).netloc, image)
    if tag != 'latest':
        image = '{0}:{1}'.format(image, tag)

    config = {
        'image': image,
        'command': ([] if raw_config.get('Entrypoint') is None else
                    raw_config['Entrypoint']),
        'args': raw_config['Cmd'],
        'env': [{'name': key, 'value': value} for key, value in
                (line.split('=', 1) for line in raw_config['Env'])],
        'ports': [{'number': int(port), 'protocol': proto} for port, proto in
                  (line.split('/', 1) for line in raw_config['ExposedPorts'])],
        'volumeMounts': ([] if raw_config.get('Volumes') is None else
                         raw_config['Volumes'].keys()),
        'workingDir': raw_config['WorkingDir'],
    }
    return config


def get_container_config(image, auth=None):
    """
    Get container config from cache or registry

    :param repo: repository name
    :param tag: tag
    :param auth: auth data. Accepts None, [<username>, <password>] or
        {'username': <username>, <password>: <password>}
    :param registry: registry address
    """
    registry, repo, tag = parse_image_name(image)
    registry = complement_registry(registry)
    if registry == DEFAULT_REGISTRY and '/' not in repo:
        repo = 'library/{0}'.format(repo)  # official dockerhub image
    if isinstance(auth, Mapping):
        auth = (auth.get('username'), auth.get('password'))

    cache_enabled = registry == DEFAULT_REGISTRY and repo.startswith('library/')
    if cache_enabled:  # for now, cache enabled only for official dockerhub repos
        image_query = '{0}/{1}:{2}'.format(registry.rstrip('/'), repo, tag)
        cached_config = DockerfileCache.query.get(image_query)
        if (cached_config is not None and
                (datetime.utcnow() - cached_config.time_stamp) < timedelta(days=1)):
            return cached_config.data

    raw_config = request_config(repo, tag, auth, registry)
    if raw_config is None:
        raise APIError('Couldn\'t get the image')
    data = prepare_response(raw_config, repo, tag, registry)

    if cache_enabled:
        if cached_config is None:
            db.session.add(DockerfileCache(image=image_query, data=data,
                                           time_stamp=datetime.utcnow()))
        else:
            cached_config.data = data
            cached_config.time_stamp = datetime.utcnow()
        db.session.commit()
    return data


def complement_registry(registry):
    if not urlparse(registry).scheme:
        registry = 'https://{0}'.format(registry.rstrip('/'))
    return registry


def parse_image_name(image):
    """Find registry, repo and tag in image name"""
    registry, repo, tag = DEFAULT_REGISTRY, image, 'latest'
    parts = repo.split('/', 1)
    if '.' in parts[0] and len(parts) == 2:
        registry, repo = parts
    if ':' in repo:
        repo, tag = repo.rsplit(':', 1)
    if '/' not in repo and registry == DEFAULT_REGISTRY:
        repo = 'library/{0}'.format(repo)
    return registry, repo, tag


def check_images_availability(images, secrets=()):
    defaults = {'registry': DEFAULT_REGISTRY, 'v2': True, 'auth': None}
    secrets = [dict(
        defaults, auth=(secret['username'], secret['password']),
        registry=complement_registry(secret.get('registry') or DEFAULT_REGISTRY)
    ) for secret in secrets]

    for image in images:
        registry, repo, tag = parse_image_name(image)
        registry = complement_registry(registry)

        s = requests.Session()
        s.verify = False  # FIXME: private registries with self-signed certs

        # iterate over all secrets + one try without auth
        for secret in secrets + [dict(defaults, registry=registry)]:
            if urlparse(secret['registry']).netloc != urlparse(registry).netloc:
                continue

            if secret['v2']:  # try V2 API
                url = get_url(registry, 'v2', repo, 'manifests', tag)
                response = s.get(url, auth=DockerAuth(secret['auth']))
                if response.status_code == 200:
                    break
                secret['v2'] = response.headers.get(
                    'docker-distribution-api-version') == 'registry/2.0'
            if not secret['v2']:
                url = get_url(registry, 'v1/repositories', repo, 'tags', tag)
                if s.get(url, auth=secret['auth']).status_code == 200:
                    break
        else:  # loop finished without breaks
            raise APIError('image {0} is not available'.format(image))
