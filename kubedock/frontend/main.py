from flask import Blueprint, render_template, session
from flask.ext.login import current_user, login_required

#from ..utils import JSONDefaultEncoder
from ..billing import Package, ExtraTax, PackageKube, Kube
from ..kapi.podcollection import PodCollection
from ..settings import TEST, KUBERDOCK_INTERNAL_USER
from ..utils import all_request_params

from kubedock.static_pages.models import MenuItem
from kubedock.kapi.notifications import read_role_events
from ..kapi import nodes as kapi_nodes


main = Blueprint('main', __name__)


@main.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if current_user.is_administrator():
        params = return_nodes()
        params['destination'] = 'nodes'
        params['administrator'] = True
    else:
        params = return_pods()
        params['destination'] = 'pods'
        params['administrator'] = False
    params['impersonated'] = False if session.get('auth_by_another') is None else True
    params['menu'] = MenuItem.get_menu()
    params['current_username'] = current_user.username
    params['adviseCollection'] = read_role_events(current_user.role)
    return render_template('index.html', params=params)

def return_pods():
    post_desc = all_request_params().get('postDescription', '')
    coll = PodCollection(current_user).get(as_json=False)
    packages = [package.to_dict() for package in Package.query.all()]
    extra_taxes_list = [e.to_dict() for e in ExtraTax.query.all()]
    extra_taxes = {e.pop('key'): e for e in extra_taxes_list}
    package_kubes = []
    kube_types = []
    user_profile = current_user.to_dict(for_profile=True)
    for pk in PackageKube.query.filter(PackageKube.package_id == current_user.package_id).all():
        package_kubes.append(pk.to_dict())
        kube_types.append(pk.kube.to_dict())
    if current_user.username == KUBERDOCK_INTERNAL_USER:
        kube_types = [kube.to_dict() for kube in Kube.query]


    return {
        'podCollection': coll,
        'kubeTypes': kube_types,
        'packages': packages,
        'extraTaxes': extra_taxes,
        'packageKubes': package_kubes,
        'userPackage': current_user.package_id,
        'postDescription': post_desc,
        'userProfile': user_profile}

def return_nodes():
    return {
        'nodeCollection': kapi_nodes.get_nodes_collection(),
        'kubeTypes': [{'id': x.id, 'name': x.name} for x in Kube.public_kubes()],
        #'userActivity': current_user.user_activity(),
        #'onlineUsersCollection': User.get_online_collection(),
    }


@main.route('/test', methods=['GET'])
def run_tests():
    if TEST:
        return render_template('t/pod_index.html')
    return "not found", 404
