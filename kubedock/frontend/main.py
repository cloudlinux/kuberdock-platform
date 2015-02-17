import json
from flask import Blueprint, render_template
from flask.ext.login import current_user, login_required

# from ..settings import APP_ROOT
from ..kubedata.kuberesolver import KubeResolver


main = Blueprint('main', __name__)


@main.route('/')
@login_required
def index():
    units = KubeResolver().resolve_all()
    # with open('{0}/kubedata/list_units.json'.format(APP_ROOT), 'r') as f:
    #     units = json.loads(f.read())
    if current_user.is_administrator():
        return render_template('index.html', pod_collection=json.dumps(units))
    return render_template(
        'index.html',
        pod_collection=json.dumps(filter((lambda x: x['owner'] == current_user.username), units)))