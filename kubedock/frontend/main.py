import json
from flask import Blueprint, render_template, redirect, url_for
from flask.ext.login import current_user, login_required

from ..api.pods import get_pods_collection
from ..billing import Kube, Package, ExtraTax


main = Blueprint('main', __name__)


@main.route('/')
@login_required
def index():
    # In setup KuberDock admin has no access to pods pages (AC-228)
    if current_user.is_administrator():
        return redirect(url_for('nodes.index'))

    coll = get_pods_collection()
    packages = [package.to_dict() for package in Package.query.all()]
    kube_types = [kube.to_dict() for kube in Kube.query.all()]
    extra_taxes_list = [e.to_dict() for e in ExtraTax.query.all()]
    extra_taxes = {e.pop('key'): e for e in extra_taxes_list}
    return render_template(
        'index.html',
        pod_collection=json.dumps(coll),
        kube_types=kube_types,
        packages=packages,
        extra_taxes=extra_taxes
    )
