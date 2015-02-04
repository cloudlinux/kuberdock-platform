from flask import render_template
from flask import jsonify
from rbac.context import PermissionDenied
from flask.ext.login import current_user

from .. import factory
from .. import sessions
from ..rbac import get_user_role
from . import assets
from ..api import APIError
import datetime


def create_app(settings_override=None):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    app.session_interface = sessions.ManagedSessionInterface(
        sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
        skip_paths, datetime.timedelta(days=1))
    assets.init_app(app)
    
    # registering blueprings
    from .main import main
    from .auth import auth
    from .minions import minions
    from .users import users
    from .notifications import notifications
    from .static_pages import static_pages

    for bp in main, auth, minions, users, notifications, static_pages:
        app.register_blueprint(bp)

    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)
    
    if not app.debug:
        for e in [500, 404]:
            app.errorhandler(e)(handle_error)
    return app


def on_app_error(e):
    return jsonify({'status': e.message}), e.status_code


def handle_error(e):
    return render_template('errors/%s.html' % e.code), e.code


def on_permission_denied(e):
    message = e.kwargs['message'] or 'Denied to {0}'.format(get_user_role())
    return message, 403