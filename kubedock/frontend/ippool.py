import json
from flask import Blueprint, render_template
from flask.ext.login import login_required

from ..kapi.ippool import IpAddrPool


ippool = Blueprint('ippool', __name__)


@ippool.route('/ippool/', strict_slashes=False)
@ippool.route('/ippool/<path:net>', strict_slashes=False)
@login_required
def index(net=None):
    """Returns the index page."""
    networks_collection = IpAddrPool().get(net)
    return render_template(
        'ippool/index.html', networks_collection=json.dumps(networks_collection))