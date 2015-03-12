import json
from flask import Blueprint, render_template
from flask.ext.login import login_required

from ..api import ippool as api_ippool


ippool = Blueprint('ippool', __name__)


@ippool.route('/ippool/')
@ippool.route('/ippool/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    networks_collection = json.dumps(api_ippool.get_networks_collection())
    return render_template(
        'ippool/index.html', networks_collection=networks_collection)

