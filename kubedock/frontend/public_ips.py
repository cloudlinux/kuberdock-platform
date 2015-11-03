import json
from flask import Blueprint, render_template
from flask.ext.login import login_required, current_user

public_ips = Blueprint('public_ips', __name__, url_prefix='/publicIPs')


@public_ips.route('/')
@public_ips.route('/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    return render_template('public_ips/index.html')
