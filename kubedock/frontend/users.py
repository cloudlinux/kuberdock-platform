import json
from flask import Blueprint, render_template, session, current_app, redirect, flash
from flask.ext.login import login_user, logout_user, current_user, login_required

from ..api import users as api_users
from ..rbac.models import Role
from ..billing import Kube
from ..users.models import User
from ..users.utils import mark_online
from ..users.signals import user_logged_out_by_another


users = Blueprint('users', __name__)


@users.before_app_request
def mark_current_user_online():
    if hasattr(current_user, 'id'):
        mark_online(current_user.id)


@users.route('/users/')
@users.route('/users/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    roles = Role.all()
    return render_template(
        'users/index.html', roles=roles,
        users_collection=api_users.get_users_collection(),
        online_users_collection=User.get_online_collection(),
        user_activity=current_user.user_activity(),
        kube_types={k.id: k.name for k in Kube.query.all()}
    )


@users.route('/users/online/')
@users.route('/users/online/<path:p>/', endpoint='online_other')
@login_required
def online_users(**kwargs):
    return index(**kwargs)


@users.route('/users/logoutA/', methods=['GET'])
# @login_required_or_basic
# @check_permission('auth_by_another', 'users')
def logout_another():
    admin_user_id = session.pop('auth_by_another', None)
    current_app.logger.debug('logout_another({0})'.format(admin_user_id))
    user_id = current_user.id
    logout_user()
    flash('You have been logged out')
    if admin_user_id is None:
        current_app.logger.warning('Session key not defined "auth_by_another"')
        return redirect('/')
    user = User.query.get(admin_user_id)
    if user is None:
        current_app.logger.warning(
            'User with Id {0} does not exist'.format(admin_user_id))
    login_user(user)
    current_app.logger.debug(
        'logout_another({0}) after'.format(current_user.id))
    user_logged_out_by_another.send((user_id, admin_user_id))
    return redirect('/users/')


