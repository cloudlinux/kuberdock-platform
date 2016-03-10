from flask import Blueprint
from kubedock.decorators import login_required_or_basic_or_token, maintenance_protected, registered_host_required
from kubedock.utils import KubeUtils
from kubedock.system_settings.models import SystemSettings
from kubedock.billing.whmcs import BillingWHMCS
from kubedock.billing.no_billing import NoBilling


billing = Blueprint('billing', __name__, url_prefix='/billing')


@billing.route('/info', methods=['GET'], strict_slashes=False)
@login_required_or_basic_or_token
@registered_host_required
@maintenance_protected
@KubeUtils.jsonwrap
def get_billing_info():
    data = KubeUtils._get_params()
    user = KubeUtils._get_current_user()
    billing_system = _get_billing()
    return billing_system.get_info(data, user)


@billing.route('/paymentmethods', methods=['GET'], strict_slashes=False)
@login_required_or_basic_or_token
@registered_host_required
@maintenance_protected
@KubeUtils.jsonwrap
def payment_methods():
    billing_system = _get_billing()
    return billing_system.get_payment_methods()


@billing.route('/order', methods=['POST'], strict_slashes=False)
@login_required_or_basic_or_token
@registered_host_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_product():
    data = KubeUtils._get_params()
    user = KubeUtils._get_current_user()
    billing_system = _get_billing()

    if data.get('pod'):
        return billing_system.order_pod(data, user=user)
    return billing_system.order_product(data)


@billing.route('/orderKubes', methods=['POST'], strict_slashes=False)
@login_required_or_basic_or_token
@maintenance_protected
@KubeUtils.jsonwrap
def order_kubes():
    data = KubeUtils._get_params()
    user = KubeUtils._get_current_user()
    billing_system = _get_billing()

    return billing_system.order_kubes(data, user=user)


def _get_billing():
    billings = {
        'no billing': NoBilling,
        'WHMCS': BillingWHMCS,
    }
    billing_type = SystemSettings.get_by_name('billing_type')
    return billings.get(billing_type, NoBilling)()
