from flask import Blueprint, render_template, session, request, flash, current_app, redirect
from flask.ext.login import current_user, login_required, login_user, logout_user

#from ..utils import JSONDefaultEncoder
from ..billing import Package, ExtraTax, PackageKube, Kube
from ..kapi.podcollection import PodCollection
from ..settings import TEST, KUBERDOCK_INTERNAL_USER
from ..utils import all_request_params

from kubedock.static_pages.models import MenuItem
from kubedock.users.models import User
from kubedock.kapi.notifications import read_role_events
from ..kapi import node_utils
from .auth import login
from kubedock.users.signals import user_logged_out_by_another

main = Blueprint('main', __name__)


@main.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.form.get('token'):
        login()
    if current_user.is_administrator():
        params = return_nodes()
        params['destination'] = 'nodes'
    else:
        params = return_pods()
        params['destination'] = 'pods'
    params['impersonated'] = False if session.get('auth_by_another') is None else True
    params['menu'] = MenuItem.get_menu()
    params['current_username'] = current_user.username
    params['user'] = current_user.to_dict(for_profile=True)
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
        'postDescription': post_desc}


def return_nodes():
    return {
        'nodeCollection': node_utils.get_nodes_collection(),
        'kubeTypes': [{'id': x.id, 'name': x.name} for x in Kube.public_kubes()],
        #'userActivity': current_user.user_activity(),
        #'onlineUsersCollection': User.get_online_collection(),
    }


@main.route('/logoutA/', methods=['GET'])
@login_required
# @check_permission('auth_by_another', 'users')
def logout_another():
    admin_user_id = session.pop('auth_by_another', None)
    user_id = current_user.id
    logout_user()
    flash('You have been logged out')
    if admin_user_id is None:
        current_app.logger.warning('Session key not defined "auth_by_another"')
        return redirect('/')
    user = User.query.get(admin_user_id)
    if user is None:
        current_app.logger.warning(
            'User with Id {0} does not exist'.format(admin_user_id))
    login_user(user)
    user_logged_out_by_another.send((user_id, admin_user_id))
    return redirect('/')


#@main.route('/test', methods=['GET'])
#def run_tests():
#    if TEST:
#        return render_template('t/pod_index.html')
#    return "not found", 404
