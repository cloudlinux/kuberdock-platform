import json
from flask import Blueprint, render_template
from flask.ext.login import current_user, login_required

from . import route
from ..core import db
from ..api import users
from ..users.models import User, Role
from ..users.utils import mark_online


bp = Blueprint('users', __name__)


@bp.before_app_request
def mark_current_user_online():
    if hasattr(current_user, 'id'):
        mark_online(current_user.id)


@route(bp, '/users/')
@route(bp, '/users/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    roles = Role.all()
    return render_template(
        'users/index.html', roles=roles,
        users_collection=json.dumps(users.get_users_collection()),
        online_users_collection=User.get_online_collection(to_json=True),
        user_activity=current_user.user_activity())


@login_required
@route(bp, '/users/online/')
@route(bp, '/users/online/<path:p>/', endpoint='online_other')
def online_users(**kwargs):
    return index(**kwargs)
