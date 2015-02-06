from flask import render_template
#from flask.ext.login import login_required, current_user
#from flask import jsonify
#from rbac.context import PermissionDenied

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
    
    # registering blueprings
    from .main import main
    from .auth import auth
    from .minions import minions
    from .users import users
    from .notifications import notifications
    from .static_pages import static_pages

    for bp in main, auth, minions, users, notifications, static_pages:
        app.register_blueprint(bp)
    
    if not app.debug:
        for e in [500, 404]:
            app.errorhandler(e)(handle_error)
    return app


def handle_error(e):
    return render_template('errors/%s.html' % e.code), e.code