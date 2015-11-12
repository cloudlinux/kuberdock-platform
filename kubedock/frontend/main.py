import json
from flask import Blueprint, render_template, redirect, url_for
from flask.ext.login import current_user, login_required

#from ..utils import JSONDefaultEncoder
from ..billing import Package, ExtraTax, PackageKube, Kube
from ..kapi.podcollection import PodCollection
from ..settings import TEST, KUBERDOCK_INTERNAL_USER
from ..utils import all_request_params


main = Blueprint('main', __name__)


@main.route('/', methods=['GET', 'POST'])
@login_required
def index():
    post_desc = all_request_params().get('postDescription', '')
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
    if current_user.username == KUBERDOCK_INTERNAL_USER:
        kube_types = [kube.to_dict() for kube in Kube.query]

    return render_template(
        'index.html',
        #pod_collection=json.dumps(coll, cls=JSONDefaultEncoder),
        pod_collection=coll,
        kube_types=kube_types,
        packages=packages,
        extra_taxes=extra_taxes,
        package_kubes=package_kubes,
        user_package=current_user.package_id,
        post_desc=post_desc,
    )


@main.route('/test', methods=['GET'])
def run_tests():
    if TEST:
        return render_template('t/pod_index.html')
    return "not found", 404
