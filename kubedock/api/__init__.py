from functools import wraps
from flask.ext.login import login_required, current_user
from flask import jsonify
from rbac.context import PermissionDenied

from ..utils import JSONEncoder
from .. import factory
from .. import sessions
import datetime


def create_app(settings_override=None):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    app.session_interface = sessions.ManagedSessionInterface(
        sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
        skip_paths, datetime.timedelta(days=1))
    app.json_encoder = JSONEncoder
    app.errorhandler(404)(on_404)
    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)
    return app


def route(bp, *args, **kwargs):
    kwargs.setdefault('strict_slashes', False)
    def decorator(f):
        @bp.route(*args, **kwargs)
        @login_required
        @wraps(f)
        def wrapper(*args, **kwargs):
            sc = 200
            rv = f(*args, **kwargs)
            if isinstance(rv, tuple):
                sc = rv[1]
                rv = rv[0]
            #return jsonify(dict(data=rv)), sc
            return rv, sc
        return f
    return decorator


def noauthroute(bp, *args, **kwargs):
    def decorator(f):
        @bp.route(*args, **kwargs)
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return f
    return decorator


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
