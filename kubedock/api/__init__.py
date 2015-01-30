import datetime
#from ..utils import JSONEncoder
from .. import factory
from .. import sessions

from flask.ext.login import current_user
from flask import jsonify
from rbac.context import PermissionDenied


def create_app(settings_override=None):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    app.session_interface = sessions.ManagedSessionInterface(
        sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
        skip_paths, datetime.timedelta(days=1))
    
    # registering blueprings
    from .images import images
    from .pods import pods
    from .stream import stream
    from .minions import minions
    from .stats import stats
    from .users import users
    from .notifications import notifications
    from .static_pages import static_pages

    for bp in images, pods, stream, minions, stats, users, notifications, \
              static_pages:
        app.register_blueprint(bp)
        
    #app.json_encoder = JSONEncoder
    app.errorhandler(404)(on_404)
    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)
    return app


class APIError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code


def on_app_error(e):
    return jsonify({'status': e.message}), e.status_code


def on_permission_denied(e):
    # TODO(Stanislav) change to correct roleloader()
    message = e.kwargs['message'] or 'Denied to {0}'.format(current_user.role.rolename)
    return on_app_error(APIError('Error. {0}'.format(message), status_code=403))


def on_404(e):
    return on_app_error(APIError('Not found', status_code=404))
