import datetime

from flask import jsonify
from fabric.api import env, run, put, output

from .. import factory
from .. import sessions
from ..utils import APIError
from kubedock.settings import SSH_KEY_FILENAME


def create_app(settings_override=None, fake_sessions=False):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    if fake_sessions:
        app.session_interface = sessions.FakeSessionInterface()
    else:
        app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
            skip_paths, datetime.timedelta(days=1))

    # registering blueprings
    from .images import images
    from .stream import stream
    from .nodes import nodes
    from .stats import stats
    from .users import users
    from .notifications import notifications
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

    for bp in (images, stream, nodes, stats, users, notifications, yamlapi,
               usage, pricing, ippool, settings, podapi, auth,
               pstorage, predefined_apps, logs, hosts):
        app.register_blueprint(bp)

    app.errorhandler(404)(on_404)
    app.errorhandler(APIError)(on_app_error)

    return app


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
    return jsonify({
        'status': 'error',
        'data': e.message,
        'type': getattr(e, 'type', e.__class__.__name__)
    }), e.status_code


def on_404(e):
    return on_app_error(APIError('Not found', status_code=404, type='NotFound'))
