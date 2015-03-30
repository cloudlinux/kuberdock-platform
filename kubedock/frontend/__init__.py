import datetime
from flask import render_template
from flask import jsonify
from sqlalchemy.ext.automap import automap_base
from rbac.context import PermissionDenied

from .. import factory
from .. import sessions
from ..rbac import init_permissions, get_user_role
from ..utils import APIError
from ..core import db
from . import assets


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
    from .nodes import nodes
    from .users import users
    from .notifications import notifications
    from .static_pages import static_pages
    from .ippool import ippool
    from .settings import settings

    for bp in main, auth, nodes, users, notifications, static_pages, ippool, \
            settings:
        app.register_blueprint(bp)

    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)
    
    if not app.debug:
        for e in [500, 404]:
            app.errorhandler(e)(handle_error)

    # context processors
    from ..users.context_processors import users_helpers
    from ..static_pages.context_processors import pages_helpers
    app.context_processor(users_helpers)
    app.context_processor(pages_helpers)

    with app.app_context():
        Base = automap_base()
        Base.prepare(db.engine, reflect=True)
        app.extensions['models'] = Base.classes
        init_permissions()

    return app


def on_app_error(e):
    return jsonify({'status': e.message}), e.status_code


def handle_error(e):
    return render_template('errors/%s.html' % e.code), e.code


def on_permission_denied(e):
    message = e.kwargs['message'] or 'Denied to {0}'.format(get_user_role())
    return message, 403