from flask import Blueprint, render_template
import json
from . import route
from ..api import minions

bp = Blueprint('minions', __name__)


@route(bp, '/minions/')
@route(bp, '/minions/<path:p>/', endpoint='other')
def index(**kwargs):
    return render_template('minions/index.html', minions_collection=json.dumps(minions.get_minions_collection()))

