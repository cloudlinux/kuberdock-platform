from flask import Blueprint, render_template
import json
from . import route
from ..models import Role
from ..core import db
from ..api import users

bp = Blueprint('users', __name__)


@route(bp, '/users/')
@route(bp, '/users/<path:p>/', endpoint='other')
def index(**kwargs):
    """Returns the index page."""
    roles = db.session.query(Role).all()
    return render_template('users/index.html', roles=roles, users_collection=json.dumps(users.get_users_collection()))