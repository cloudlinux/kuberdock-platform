import json
from flask import Blueprint, render_template
from flask.ext.login import login_required

from ..rbac import check_permission
from ..kapi.ippool import IpAddrPool
from ..settings import TEST


ippool = Blueprint('ippool', __name__, url_prefix='/ippool')


@ippool.route('/', strict_slashes=False)
@ippool.route('/<path:net>', strict_slashes=False)
@check_permission('view', 'ippool')
@login_required
def index(net=None):
    """Returns the index page."""
    networks_collection = IpAddrPool().get(net)
    return render_template(
        'ippool/index.html', networks_collection=json.dumps(networks_collection))

@ippool.route('/test', methods=['GET'])
def run_tests():
    if TEST:
        return render_template('t/ippool_index.html')
    return "not found", 404