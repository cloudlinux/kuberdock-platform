# -*- coding: utf-8 -*-
import json
import re
import requests
from urlparse import urlparse, parse_qsl
from collections import Mapping, defaultdict
from datetime import datetime
from urllib import urlencode

from ..core import db
from ..pods.models import DockerfileCache
from ..utils import APIError
from ..settings import DEFAULT_REGISTRY, DOCKER_IMG_CACHE_TIMEOUT


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
        """
        Try to complete the challenge.

        :param chal: challenge string
        :returns: token or None
        """
        url = urlparse(chal.pop('realm'))
        query = urlencode(dict(parse_qsl(url.query), **chal))
        url = url._replace(query=query).geturl()
        auth = None if self.username is None else (self.username, self.password)
        response = requests.get(url, auth=auth)
        data = _json_or_none(response)
        if isinstance(data, dict):
            return data.get('token')

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


def docker_auth_v1(session, registry, repo, auth):
    """
    Docker Registry v1 authentication (using both token and session)

    :param session: requests.Session object
    :param registry: full registry address (https://quay.io)
    :param repo: repo name including "namespace" (library/nginx)
    :param auth: (username, password) or None
    :returns: True if auth was successful otherwise False
    """
    if registry == DEFAULT_REGISTRY:  # dockerhub have index on different host
        registry = 'https://index.docker.io'
    url = get_url(registry, 'v1/repositories', repo, 'images')
    response = session.get(url, auth=auth, headers={'x-docker-token': 'true'})
    if response.status_code != 200:
        return False
    token = response.headers.get('x-docker-token')
    if token:
        session.headers['authorization'] = 'Token {0}'.format(token)
    return True


def get_url(base, *path):
    return urlparse(base)._replace(path='/'.join(path)).geturl()


def _json_or_none(response):
    try:
        return response.json()
    except ValueError:
        pass


def request_config(repo, tag='latest', auth=None, registry=DEFAULT_REGISTRY):
    """
    Get container config from image manifest using Docker Registry API v2 or
    from image/json using Docker Registry API v1.

    :param repo: repo name including "namespace" (library/nginx)
    :param tag: image tag
    :param auth: (username, password) or None
    :param registry: full registry address (https://quay.io)
    :returns: container config or None
    """
    s = requests.Session()
    s.verify = False  # FIXME: private registries with self-signed certs

    # try V2 API
    url = get_url(registry, 'v2', repo, 'manifests', tag)
    try:
        v2_data = _json_or_none(s.get(url, auth=DockerAuth(auth)))
        try:
            return json.loads(v2_data['history'][0]['v1Compatibility'])['config']
        except (ValueError, KeyError, TypeError):
            pass
    except requests.RequestException:
        pass

    # v2 API is not available or has some weird auth method. Let's try v1 API
    try:
        docker_auth_v1(s, registry, repo, auth)
        url = get_url(registry, 'v1/repositories', repo, 'tags', tag)
        image_id = _json_or_none(s.get(url, auth=auth))  # get image id for the tag
        if isinstance(image_id, basestring):
            url = get_url(registry, 'v1/images', image_id, 'json')
            data = _json_or_none(s.get(url, auth=auth))  # get image info
            try:
                return data['config']
            except (KeyError, TypeError):
                pass
    except requests.RequestException:
        pass


def prepare_response(raw_config, image, tag, registry=DEFAULT_REGISTRY, auth=None):
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
        'args': [] if raw_config.get('Cmd') is None else raw_config['Cmd'],
        'env': [{'name': key, 'value': value} for key, value in
                (line.split('=', 1) for line in raw_config['Env'])],
        'ports': [{'number': int(port), 'protocol': proto} for port, proto in
                  (line.split('/', 1) for line in raw_config['ExposedPorts'])],
        'volumeMounts': ([] if raw_config.get('Volumes') is None else
                         raw_config['Volumes'].keys()),
        'workingDir': raw_config['WorkingDir'],
    }
    if auth is not None:
        config['secret'] = {'username': auth[0], 'password': auth[1]}
    return config


def get_container_config(image, auth=None, refresh_cache=False):
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

    image_query = '{0}/{1}:{2}'.format(registry.rstrip('/'), repo, tag)
    cached_config = DockerfileCache.query.get(image_query)
    if (not refresh_cache and cached_config is not None and
            (datetime.utcnow() - cached_config.time_stamp) < DOCKER_IMG_CACHE_TIMEOUT):
        return cached_config.data

    raw_config = request_config(repo, tag, auth, registry)
    if raw_config is None:
        raise APIError('Couldn\'t get the image')
    data = prepare_response(raw_config, repo, tag, registry, auth)

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
    # TODO: improve parsing, add hash
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
    """
    Check if all images are available using provided credentials.

    :param images: list of images
    :param secrets: list of secrets
    :raises APIError: if some image is not available
    """
    registries = defaultdict(lambda: {'v2_available': True, 'auth': [None]})
    for secret in secrets:
        username, password, registry = secret
        registry = complement_registry(registry)
        registries[registry]['auth'].append((username, password))

    for image in images:
        _check_image_availability(image, registries)


def _check_image_availability(image, registries):
    registry_url, repo, tag = parse_image_name(image)
    registry_url = complement_registry(registry_url)
    registry = registries[registry_url]

    for auth in registry['auth']:
        s = requests.Session()
        s.verify = False  # FIXME: private registries with self-signed certs

        # For now too many registries don't support
        # Docker Registry v2 API, so we'll try v1 first.
        try:
            if docker_auth_v1(s, registry_url, repo, auth):
                url = get_url(registry_url, 'v1/repositories', repo, 'tags', tag)
                response = s.get(url, auth=auth)
                if s.get(url, auth=auth).status_code == 200:
                    return True
        except requests.RequestException:
            pass

        if registry['v2_available']:  # if v1 didn't work and v2 is available
            url = get_url(registry_url, 'v2', repo, 'manifests', tag)
            try:
                response = s.get(url, auth=DockerAuth(auth))
                if response.status_code == 200:
                    return True
                # remember if v2 is not available at all
                registry['v2_available'] = response.headers.get(
                    'docker-distribution-api-version') == 'registry/2.0'
            except requests.RequestException:
                pass
    raise APIError('image {0} is not available'.format(image))
