import json
from flask import Blueprint, render_template
from flask.ext.login import current_user

from ..api import users as api_users
from ..users.models import User, Role
from ..users.utils import mark_online


users = Blueprint('users', __name__)


@users.before_app_request
def mark_current_user_online():
    if hasattr(current_user, 'id'):
        mark_online(current_user.id)


@users.route('/users/')
@users.route('/users/<path:p>/', endpoint='other')
def index(**kwargs):
    """Returns the index page."""
    roles = Role.all()
    return render_template(
        'users/index.html', roles=roles,
        users_collection=json.dumps(api_users.get_users_collection()),
        online_users_collection=User.get_online_collection(to_json=True),
        user_activity=current_user.user_activity())


@users.route('/users/online/')
@users.route('/users/online/<path:p>/', endpoint='online_other')
def online_users(**kwargs):
    return index(**kwargs)
