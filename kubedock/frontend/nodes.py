from flask import Blueprint, render_template
from flask.ext.login import login_required
import json
from ..api import nodes as api_nodes

nodes = Blueprint('nodes', __name__)


@nodes.route('/nodes/')
@nodes.route('/nodes/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    return render_template(
        'nodes/index.html',
        nodes_collection=json.dumps(api_nodes.get_nodes_collection()))

