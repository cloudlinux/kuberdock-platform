import json
from flask import Blueprint, render_template
from flask.ext.login import current_user, login_required

from ..api.pods import get_pods_collection


main = Blueprint('main', __name__)


@main.route('/')
@login_required
def index():
    coll = get_pods_collection()
    return render_template('index.html', pod_collection=json.dumps(coll))
