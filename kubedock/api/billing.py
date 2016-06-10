from flask import Blueprint, current_app

from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError
from kubedock.login import auth_required
from kubedock.utils import KubeUtils
from kubedock.billing.models import Package, Kube
from kubedock.system_settings.models import SystemSettings


billing = Blueprint('billing', __name__, url_prefix='/billing')


def no_billing_data():
    return {
        'billing': 'No billing',
        'packages': [p.to_dict(with_kubes=True) for p in Package.query.all()],
        'default': {
            'kubeType': Kube.get_default_kube().to_dict(),
            'packageId': Package.get_default().to_dict(),
        }
    }


@billing.route('/info', methods=['GET'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def get_billing_info():
    data = KubeUtils._get_params()
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        return no_billing_data()
    billing = current_app.billing_factory.get_billing(current_billing)
    return billing.getkuberdockinfo(**data)


@billing.route('/paymentmethods', methods=['GET'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def payment_methods():
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise APIError('Without billing', 404)
    billing = current_app.billing_factory.get_billing(current_billing)
    return billing.getpaymentmethods()


@billing.route('/order', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_product():
    data = KubeUtils._get_params()
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise APIError('Without billing', 404)
    billing = current_app.billing_factory.get_billing(current_billing)
    if data.get('pod'):
        data['referer'] = data['referer'] if 'referer' in data else ''
        return billing.orderpod(**data)
    return billing.orderproduct(**data)


@billing.route('/orderPodEdit', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_edit():
    # TODO: actual billing method
    # return {'status': 'Unpaid', 'redirect': 'http://i.am.the.billing.com'}
    user = KubeUtils._get_current_user()
    data = KubeUtils._get_params()
    from kubedock.kapi.podcollection import PodCollection, POD_STATUSES
    pc = PodCollection(user)
    status = pc._get_by_id(data['pod']['id']).status
    cmd = 'start' if status == POD_STATUSES.stopped else 'redeploy'
    pc.update(data['pod']['id'], {'command': cmd,
                                  'commandOptions': {'applyEdit': True}})
    return {'status': 'Paid'}


@billing.route('/orderKubes', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_kubes():
    data = KubeUtils._get_params()
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise APIError('Without billing', 404)
    billing = current_app.billing_factory.get_billing(current_billing)
    data['referer'] = data['referer'] if 'referer' in data else ''
    return billing.orderkubes(**data)
