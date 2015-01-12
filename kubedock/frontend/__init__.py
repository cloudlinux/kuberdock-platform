from flask import render_template
from functools import wraps
from flask.ext.login import login_required

from .. import factory
from .. import sessions
from . import assets
import datetime

def create_app(settings_override=None):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    app.session_interface = sessions.ManagedSessionInterface(
        sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
        skip_paths, datetime.timedelta(days=1))
    assets.init_app(app)
    if not app.debug:
        for e in [500, 404]:
            app.errorhandler(e)(handle_error)
    return app

def handle_error(e):
    return render_template('errors/%s.html' % e.code), e.code


def route(bp, *args, **kwargs):
    def decorator(f):
        @bp.route(*args, **kwargs)
        @login_required
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
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