from flask import Blueprint, render_template
from . import route
from flask.ext.login import current_user
import json

from ..kubedata import KubeResolver

bp = Blueprint('main', __name__)

@route(bp, '/')
def index():
    units = KubeResolver().resolve_all()
    if current_user.is_administrator():
        return render_template('index.html', pod_collection=json.dumps(units))
    return render_template(
        'index.html',
        pod_collection=json.dumps(filter((lambda x: x['owner'] == current_user.username), units)))