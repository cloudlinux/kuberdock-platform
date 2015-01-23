from functools import wraps
from flask import jsonify
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
    return app


def route(bp, *args, **kwargs):
    kwargs.setdefault('strict_slashes', False)
    def decorator(f):
        @bp.route(*args, **kwargs)
        @login_required
        @wraps(f)
        def wrapper(*args, **kwargs):
            sc = 200
            try:
                rv = f(*args, **kwargs)
            except PermissionDenied as e:
                message = e.kwargs['message'] or 'Denied to {0}'.format(current_user.role.rolename)
                return jsonify({'status': 'ERROR', 'data': message}), 403
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


def on_app_error(e):
    return jsonify(dict(error=e.msg)), 400


def on_404(e):
    return jsonify(dict(error='Not found')), 404
