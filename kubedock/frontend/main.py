import json
from flask import Blueprint, render_template, redirect, url_for
from flask.ext.login import current_user, login_required

#from ..utils import JSONDefaultEncoder
from ..billing import Kube, Package, ExtraTax, PackageKube
from ..kapi.podcollection import PodCollection
from ..settings import TEST


main = Blueprint('main', __name__)


@main.route('/')
@login_required
def index():
    # In setup KuberDock admin has no access to pods pages (AC-228)
    if current_user.is_administrator():
        return redirect(url_for('nodes.index'))
    coll = PodCollection(current_user).get()
    packages = [package.to_dict() for package in Package.query.all()]
    extra_taxes_list = [e.to_dict() for e in ExtraTax.query.all()]
    extra_taxes = {e.pop('key'): e for e in extra_taxes_list}
    package_kubes = []
    kube_types = []
    for pk in PackageKube.query.filter(PackageKube.package_id == current_user.package_id).all():
        package_kubes.append(pk.to_dict())
        kube_types.append(pk.kubes.to_dict())

    return render_template(
        'index.html',
        #pod_collection=json.dumps(coll, cls=JSONDefaultEncoder),
        pod_collection=coll,
        kube_types=kube_types,
        packages=packages,
        extra_taxes=extra_taxes,
        package_kubes=package_kubes,
        user_package=current_user.package_id
    )


@main.route('/test', methods=['GET'])
def run_tests():
    if TEST:
        return render_template('t/pod_index.html')
    return "not found", 404