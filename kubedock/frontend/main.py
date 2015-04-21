import json
from flask import Blueprint, render_template
from flask.ext.login import current_user, login_required

from ..api.pods import get_pods_collection
from ..billing import Kube


main = Blueprint('main', __name__)


@main.route('/')
@login_required
def index():
    # In setup KuberDock admin has no access to pods pages (AC-228)
    if current_user.is_administrator():
        return redirect(url_for('nodes.index'))

    coll = get_pods_collection()
    return render_template(
        'index.html',
        pod_collection=json.dumps(coll),
        kube_types=[{'id': x.id, 'name': x.name} for x in Kube.query.all()])
