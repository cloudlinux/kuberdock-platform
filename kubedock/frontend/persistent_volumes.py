import json
from flask import Blueprint, render_template
from flask.ext.login import login_required, current_user


persistent_volumes = Blueprint(
    'persistent_volumes', __name__, url_prefix='/persistent_volumes')


@persistent_volumes.route('/')
@persistent_volumes.route('/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    return render_template('persistent_volumes/index.html')
