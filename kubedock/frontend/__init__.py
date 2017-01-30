
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

from flask import render_template
from flask import jsonify

from .. import factory
from .. import sessions
from ..exceptions import APIError, PermissionDenied
from ..rbac import acl, get_user_role
from kubedock.settings import SESSION_LIFETIME


def create_app(settings_override=None, fake_sessions=False):
    app = factory.create_app(__name__, __path__, settings_override)
    if fake_sessions:
        app.session_interface = sessions.FakeSessionInterface()
    else:
        app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(), SESSION_LIFETIME)

    # registering blueprings
    from .main import main
    from .apps import apps

    for bp in main, apps:
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
