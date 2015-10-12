# -*- coding: utf-8 -*-
import json
import re
import requests
from urlparse import urlparse, parse_qsl
from collections import Mapping, defaultdict
from datetime import datetime
from urllib import urlencode

from ..core import db
from ..pods.models import DockerfileCache, PrivateRegistryFailedLogin
from ..utils import APIError
from ..settings import DEFAULT_REGISTRY


#: Minimum time in seconds to stop authentication attempts to a private
# registry after last failed login attempt
MIN_FAILED_LOGIN_PAUSE = 3

DOCKERHUB_V1_INDEX = 'https://index.docker.io'


class APIVersionError(Exception):
    """Helper exception to raise on invalid API version in a docker registry"""
    pass

class DockerAuth(requests.auth.AuthBase):
    """Docker Registry v2 authentication + HTTP Basic Auth for private
    registry.

    """
    _bearer_pat = re.compile(r'bearer ', flags=re.IGNORECASE)

    def __init__(self, username=None, password=None):
        """
        Usage:
        DockerAuth('my-username', 'my-password')
        DockerAuth(username='my-username', password='my-password')
        DockerAuth(['my-username', 'my-password'])
        without credentials:
        DockerAuth(), DockerAuth(None), DockerAuth(None, None)
        """
        if hasattr(username, '__iter__') and password is None:
            # got one iterable
            username, password = username
        self.username, self.password = username, password
        self.num_401_calls = 0
        self.original_url = None

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

        seconds_to_wait = when_next_login_allowed(
            self.username, response.request.url)
        raise_api_error_to_login_pause(seconds_to_wait)
        self.num_401_calls += 1

        method = s_auth.split()[0].lower()
        if method in ('basic', 'bearer'):
            # Consume content and release the original connection
            # to allow our new request to reuse the same one.
            response.content
            response.raw.release_conn()
            prep = response.request.copy()

            if method == 'basic' and self.username is not None:
                # private registry
                prep = requests.auth.HTTPBasicAuth(
                    self.username, self.password)(prep)
            elif method == 'bearer':  # Docker Registry v2 authentication
                chal = requests.utils.parse_dict_header(
                    self._bearer_pat.sub('', s_auth, count=1))
                token = self.get_token(chal)
                if token is not None:
                    prep.headers['Authorization'] = 'Bearer {0}'.format(token)

            new_response = response.connection.send(prep, **kwargs)
            new_response.history.append(response)
            new_response.request = prep
            if new_response.status_code == requests.codes.unauthorized:
                save_failed_login(self.username, response.request.url)
            return new_response
        return response

    def __call__(self, request):
        request.register_hook('response', self.handle_401)
        return request


def save_failed_login(username, url):
    """Remember current user name and registry in failed logins table."""
    url = url or ''
    registry = urlparse(url).netloc
    if not(username and registry):
        return
    PrivateRegistryFailedLogin(
        login=username, registry=registry, created=datetime.utcnow()
    ).save()


def when_next_login_allowed(username, url):
    """Check last failed login for current username and registry was
    earlier than minimum allowed pause for login attempts.
    Returns number of seconds we should wait.

    """
    url = url or ''
    registry = urlparse(url).netloc
    if not (username and registry):
        return 0
    last_entry = PrivateRegistryFailedLogin.query.filter(
        PrivateRegistryFailedLogin.login == username,
        PrivateRegistryFailedLogin.registry == registry,
    ).order_by(PrivateRegistryFailedLogin.created.desc()).first()
    if not last_entry:
        return 0
    timediff = datetime.utcnow() - last_entry.created
    timediff = timediff.seconds + timediff.days * 24 * 60 * 60
    if timediff >= MIN_FAILED_LOGIN_PAUSE:
        return 0
    return MIN_FAILED_LOGIN_PAUSE - timediff


def raise_api_error_to_login_pause(seconds):
    """Raises API error if specified seconds is > 0."""
    if seconds:
        raise APIError(
            'To prevent blocking of the user name wait for {0} seconds '
            'before next login attempt.'.format(seconds),
            requests.codes.too_many_requests)


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
        registry = DOCKERHUB_V1_INDEX
    username = None
    if auth and auth[0]:
        username = auth[0]
        seconds_to_wait = when_next_login_allowed(username, registry)
        raise_api_error_to_login_pause(seconds_to_wait)
    url = get_url(registry, 'v1/repositories', repo, 'images')
    response = session.get(url, auth=auth, headers={'x-docker-token': 'true'})
    if response.status_code != 200:
        if response.status_code == requests.codes.unauthorized and username:
            save_failed_login(username, url)
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


def try_v2_request_config(repo, tag, auth, registry, just_check=False):
    """Config request via V2 API
    Get container config from image manifest using Docker Registry API v2

    :param repo: repo name including "namespace" (library/nginx)
    :param tag: image tag
    :param auth: (username, password) or None
    :param registry: full registry address (https://quay.io)
    :param just_check: only check image availability, do not extract
        configuration
    :returns: container config (True if just_check=True) or None
    :raise APIVersionError: for check requests - if registry doesn't support
        api v2
    """
    s = requests.Session()
    s.verify = False  # FIXME: private registries with self-signed certs

    url = get_url(registry, 'v2', repo, 'manifests', tag)
    try:
        response = s.get(url, auth=DockerAuth(auth))
        if just_check:
            if response.status_code == 200:
                return True
            if response.headers.get('docker-distribution-api-version') !=\
                    'registry/2.0':
                raise APIVersionError()

        v2_data = _json_or_none(response)
        try:
            return json.loads(
                v2_data['history'][0]['v1Compatibility']
            )['config']
        except (ValueError, KeyError, TypeError):
            pass
    except requests.RequestException:
        pass
    return None


def try_v1_request_config(repo, tag, auth, registry, just_check=False):
    """Config request via V1 API
    Get container config from image/json using Docker Registry API v1.

    :param repo: repo name including "namespace" (library/nginx)
    :param tag: image tag
    :param auth: (username, password) or None
    :param registry: full registry address (https://quay.io)
    :param just_check: only check image availability, do not extract
        configuration
    :returns: container config (True if just_check=True) or None
    """
    s = requests.Session()
    s.verify = False  # FIXME: private registries with self-signed certs
    try:
        docker_auth_v1(s, registry, repo, auth)
        url = get_url(registry, 'v1/repositories', repo, 'tags', tag)
        response = s.get(url)
        if response.status_code == 200:
            image_id = _json_or_none(response)
            if not isinstance(image_id, basestring):
                return None
            if just_check:
                return True
            url = get_url(registry, 'v1/images', image_id, 'json')
            data = _json_or_none(s.get(url))  # get image info
            try:
                return data['config']
            except (KeyError, TypeError):
                pass
    except requests.RequestException:
        pass
    return None


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
    result = try_v2_request_config(repo, tag, auth, registry)
    if result:
        return result
    return try_v1_request_config(repo, tag, auth, registry)


def prepare_response(raw_config, image, tag, registry=DEFAULT_REGISTRY, auth=None):
    """Create api response using raw container config, image, tag and registry.
    """
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

    :param image: string represents image. May be in the following forms:
        nginx[:tag] - for offical images with tag, or latest, if tag is omitted
        username/nginx[:tag] - for public or private custom images on dockerhub
        some.hub.com/username/nginx[:tag] - for public or private images on
            3rd party registries
    :param auth: authentication data. Accepts None, [<username>, <password>] or
        {'username': <username>, <password>: <password>}
    :return: dict which represents image configuration, received from a registry
    """
    registry, repo, tag = parse_image_name(image)
    registry = complement_registry(registry)
    if registry == DEFAULT_REGISTRY and '/' not in repo:
        repo = 'library/{0}'.format(repo)  # official dockerhub image
    if isinstance(auth, Mapping):
        auth = (auth.get('username'), auth.get('password'))

    cache_enabled = auth is None
    if cache_enabled:
        image_query = '{0}/{1}:{2}'.format(registry.rstrip('/'), repo, tag)
        cached_config = DockerfileCache.query.get(image_query)
        if not (refresh_cache or cached_config is None or cached_config.outdated):
            return cached_config.data

    raw_config = request_config(repo, tag, auth, registry)
    if raw_config is None:
        raise APIError('Couldn\'t get the image')
    data = prepare_response(raw_config, repo, tag, registry, auth)

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
    Tries to check image availability wihout credentials and if it failed, will
    try all specified crenedentials for the registry until successful result.

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
        # For now too many registries don't support
        # Docker Registry v2 API, so we'll try v1 first.
        if try_v1_request_config(repo, tag, auth, registry_url, True):
            return True

        if registry['v2_available']:  # if v1 didn't work and v2 is available
            try:
                if try_v2_request_config(repo, tag, auth, registry_url, True):
                    return True
            except APIVersionError:
                registry['v2_available'] = False

    raise APIError('image {0} is not available'.format(image))
