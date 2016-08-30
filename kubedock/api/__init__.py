from functools import wraps

from fabric.api import env, run, put, output
from flask import jsonify, request, g

from kubedock.core import current_app
from kubedock.utils import KubeUtils, send_event_to_role, API_VERSIONS
from kubedock import factory
from kubedock import sessions
from kubedock.exceptions import APIError, InternalAPIError, NotFound
from kubedock.settings import SSH_KEY_FILENAME, SESSION_LIFETIME


class InvalidAPIVersion(APIError):
    def __init__(self, apiVersion=None,
                 acceptableVersions=API_VERSIONS.acceptable):
        if apiVersion is None:
            apiVersion = g.get('api_version')
        super(InvalidAPIVersion, self).__init__(details={
            'apiVersion': apiVersion,
            'acceptableVersions': acceptableVersions,
        })

    @property
    def message(self):
        apiVersion = self.details.get('apiVersion')
        acceptableVersions = ', '.join(self.details.get('acceptableVersions'))
        return (
            'Invalid api version: {apiVersion}. Acceptable versions are: '
            '{acceptableVersions}.'.format(
                apiVersion=apiVersion, acceptableVersions=acceptableVersions))


def create_app(settings_override=None, fake_sessions=False):
    app = factory.create_app(__name__, __path__, settings_override)
    if fake_sessions:
        app.session_interface = sessions.FakeSessionInterface()
    else:
        app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(), SESSION_LIFETIME)

    # registering blueprints
    from .images import images
    from .stream import stream
    from .nodes import nodes
    from .stats import stats
    from .users import users
    from .usage import usage
    from .pricing import pricing
    from .ippool import ippool
    from .settings import settings
    from .podapi import podapi
    from .yaml_api import yamlapi
    from .auth import auth
    from .pstorage import pstorage
    from .predefined_apps import predefined_apps
    from .logs import logs
    from .hosts import hosts
    from .billing import billing
    from .restore import restore
    from .domains import domains

    for bp in (images, stream, nodes, stats, users, yamlapi,
               usage, pricing, ippool, settings, podapi, auth,
               pstorage, predefined_apps, logs, hosts, billing,
               restore, domains):
        app.register_blueprint(bp)

    app.errorhandler(404)(on_404)
    app.errorhandler(APIError)(on_app_error)

    app.before_request(handle_api_version)

    return app


def handle_api_version():
    api_version = request.headers.get('kuberdock-api-version',
                                      API_VERSIONS.default)
    g.api_version = api_version
    if api_version not in API_VERSIONS.acceptable:
        return on_app_error(InvalidAPIVersion())


def pre_start_hook(app):
    from ..nodes.models import Node
    # env.warn_only = True
    env.user = 'root'
    env.key_filename = SSH_KEY_FILENAME
    output.stdout = False
    output.running = False
    PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'
    with app.app_context():
        for node in Node.query.all():
            env.host_string = node.hostname
            put('./node_network_plugin.sh', PLUGIN_DIR + 'kuberdock')
            put('./node_network_plugin.py', PLUGIN_DIR + 'kuberdock.py')
            run('systemctl restart kuberdock-watcher')
            print 'Kuberdock node parts are updated'


def on_app_error(e):
    if isinstance(e, InternalAPIError):
        current_app.logger.error(e.message, exc_info=e.exc_info)
        current_user = KubeUtils.get_current_user()
        if current_user.is_administrator():
            return _jsonify_api_error(e)
        else:
            send_event_to_role('notify:error', {'message': e.message}, 'Admin')
            return _jsonify_api_error(
                APIError(e.response_message or 'Unknown error', 500))

    elif isinstance(e, APIError):
        return _jsonify_api_error(e)

    else:  # unexpected error
        current_app.logger.exception(e.message)
        current_user = KubeUtils.get_current_user()
        if current_user.is_administrator():
            return _jsonify_api_error(APIError(repr(e), 500))
        else:
            send_event_to_role('notify:error',
                               {'message': 'Unexpected error: ' + repr(e)},
                               'Admin')
            _jsonify_api_error(
                APIError('Internal error, please contact administrator', 500))


def _jsonify_api_error(e):
    api_version = (g.api_version if g.api_version in API_VERSIONS.acceptable
                   else API_VERSIONS.default)

    if api_version == API_VERSIONS.v1:
        return jsonify({
            'status': 'error',
            'data': e.message,  # left for backwards compatibility
            'details': e.details,
            'type': e.type,
        }), e.status_code
    else:
        return jsonify({
            'status': 'error',
            'message': e.message,
            'details': e.details,
            'type': e.type,
        }), e.status_code


def on_404(e):
    return on_app_error(NotFound())


def populate_registered_hosts(app):
    import requests
    from ..settings import ETCD_REGISTERED_HOSTS
    from ..nodes.models import RegisteredHost
    from ..utils import update_nginx_proxy_restriction

    requests.delete(ETCD_REGISTERED_HOSTS, params={'recursive': True})

    with app.app_context():
        accept_ips = [registered.host for registered in RegisteredHost.query]

    for registered_host in accept_ips:
        requests.put('/'.join([ETCD_REGISTERED_HOSTS, registered_host]))

    update_nginx_proxy_restriction(accept_ips)


class check_api_version(object):
    """Check that api version in request is one of `acceptable_versions`.

    Can be used as decorator, callback (use #check method), or coerced to
    boolean.
    """
    def __init__(self, acceptable_versions):
        self.acceptable_versions = acceptable_versions

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wraps(func)(wrapper)

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def __nonzero__(self):
        return g.api_version in self.acceptable_versions

    def check(self):
        if not self:
            raise InvalidAPIVersion(
                acceptableVersions=self.acceptable_versions)
