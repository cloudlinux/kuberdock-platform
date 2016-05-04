import datetime
from flask import render_template
from flask import jsonify

from .. import factory
from .. import sessions
from ..rbac import acl, get_user_role
from ..utils import APIError, PermissionDenied


def create_app(settings_override=None, fake_sessions=False):
    app = factory.create_app(__name__, __path__, settings_override)
    if fake_sessions:
        app.session_interface = sessions.FakeSessionInterface()
    else:
        app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
            datetime.timedelta(seconds=60))

    # registering blueprings
    from .main import main
    from .auth import auth
    from .apps import apps

    for bp in main, auth, apps:
        app.register_blueprint(bp)

    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)

    if not app.debug:
        for e in [500, 404]:
            app.errorhandler(e)(handle_error)

    with app.app_context():
        acl.init_permissions()

    return app


def on_app_error(e):
    return jsonify({'status': e.message}), e.status_code


def handle_error(e):
    return render_template('errors/%s.html' % e.code), e.code


def on_permission_denied(e):
    message = e.kwargs['message'] or 'Denied to {0}'.format(get_user_role())
    return message, 403
