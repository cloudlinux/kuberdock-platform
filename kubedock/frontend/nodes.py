from flask import Blueprint, render_template
from flask.ext.login import login_required
import json
from ..kapi import node_utils
from ..billing import Kube
from ..rbac import check_permission

nodes = Blueprint('nodes', __name__)


@nodes.route('/nodes/')
@nodes.route('/nodes/<path:p>/', endpoint='other')
@login_required
@check_permission('get', 'nodes')
def index(**kwargs):
    return render_template(
        'nodes/index.html',
        nodes_collection=json.dumps(node_utils.get_nodes_collection()),
        kube_types=[{'id': x.id, 'name': x.name} for x in Kube.public_kubes()])

