import datetime
from .. import factory
from .. import sessions
from ..rbac import get_user_role
from ..utils import APIError

from flask.ext.login import current_user
from flask import jsonify
from flask.json import JSONEncoder
from rbac.context import PermissionDenied


class APIJSONEncoder(JSONEncoder):
    """Fix datetime conversion in flask.jsonify"""
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return JSONEncoder.default(self, obj)


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
    from .static_pages import static_pages
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

    for bp in (images, stream, nodes, stats, users, notifications, yamlapi,
               static_pages, usage, pricing, ippool, settings, podapi, auth,
               pstorage, predefined_apps, logs):
        app.register_blueprint(bp)

    app.json_encoder = APIJSONEncoder
    app.errorhandler(404)(on_404)
    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)

    return app


def on_app_error(e):
    return jsonify({'status': 'error', 'data': e.message}), e.status_code


def on_permission_denied(e):
    message = e.kwargs['message'] or 'Denied to {0}'.format(get_user_role())
    return on_app_error(APIError(message, status_code=403))


def on_404(e):
    return on_app_error(APIError('Not found', status_code=404))
