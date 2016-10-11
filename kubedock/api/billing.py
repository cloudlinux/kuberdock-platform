from functools import wraps

from flask import Blueprint, current_app, request

from kubedock.core import db
from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError, BillingExc
from kubedock.login import auth_required
from kubedock.utils import atomic, KubeUtils
from kubedock.billing.models import Package, Kube
from kubedock.system_settings.models import SystemSettings
from kubedock.kapi.apps import PredefinedApp, start_pod_from_yaml
from kubedock.kapi.podcollection import PodCollection
import json


billing = Blueprint('billing', __name__, url_prefix='/billing')


class WithoutBilling(APIError):
    message = 'Without billing'
    status_code = 404


def no_billing_data():
    return {
        'billing': 'No billing',
        'packages': [p.to_dict(with_kubes=True) for p in Package.query.all()],
        'default': {
            'kubeType': Kube.get_default_kube().to_dict(),
            'packageId': Package.get_default().to_dict(),
        }
    }


def with_billing(raise_=True):
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            billing_type = SystemSettings.get_by_name('billing_type')
            if billing_type == 'No billing':
                if raise_:
                    raise WithoutBilling()
                driver = None
            else:
                driver = current_app.billing_factory.get_billing(billing_type)
            return func(driver, *args, **kwargs)
        return inner
    return decorator


@billing.route('/info', methods=['GET'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing(raise_=False)
def get_billing_info(billing_driver):
    data = KubeUtils._get_params()
    if billing_driver is None:
        return no_billing_data()
    return billing_driver.getkuberdockinfo(**data)


@billing.route('/paymentmethods', methods=['GET'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def payment_methods(billing_driver):
    return billing_driver.getpaymentmethods()


@billing.route('/order', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def order_product(billing_driver):
    data = KubeUtils._get_params()
    if data.get('pod'):
        data['referer'] = data['referer'] if 'referer' in data else ''
        return billing_driver.orderpod(**data)
    return billing_driver.orderproduct(**data)


@billing.route('/orderPodEdit', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def order_edit(billing_driver):
    data = KubeUtils._get_params()
    data['pod'] = json.dumps(data['pod'])
    data['referer'] = data['referer'] if 'referer' in data else ''
    response = billing_driver.orderpodedit(**data)
    if isinstance(response, basestring):
        raise BillingExc.InternalBillingError(
            details={'message': response})
    if response.get('result') == 'error':
        raise APIError(response.get('message'))
    return response


@billing.route('/switch-app-package/<pod_id>/<int:plan_id>',
               methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def switch_app_package(billing_driver, pod_id, plan_id):
    owner = KubeUtils.get_current_user()

    transaction = db.session.begin_nested()
    with atomic():
        old_pod = PodCollection(owner).get(pod_id, as_json=True)
        PredefinedApp.update_pod_to_plan(
            pod_id, plan_id, async=False, dry_run=True)
        pod = PodCollection(owner).get(pod_id, as_json=True)
    transaction.rollback()

    data = KubeUtils._get_params()
    data['pod'] = pod
    data['oldPod'] = old_pod
    data['referer'] = data.get('referer') or ''

    return billing_driver.orderswitchapppackage(**data)


@billing.route('/orderKubes', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def order_kubes(billing_driver):
    data = KubeUtils._get_params()
    data['referer'] = data['referer'] if 'referer' in data else ''
    return billing_driver.orderkubes(**data)


@billing.route('/orderapp/<int:template_id>/<int:plan_id>',
               methods=['POST'], strict_slashes=False)
# Currently this workflow does not imply authentication but we can force it
# @auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def order_app(billing_driver, template_id, plan_id):
    data = KubeUtils._get_params()
    app = PredefinedApp.get(template_id)

    start_pod_from_yaml(app.get_filled_template_for_plan(plan_id, data),
                        dry_run=True)

    filled = app.get_filled_template_for_plan(plan_id, data, as_yaml=True)
    pkgid = app._get_package().id

    return billing_driver.orderapp(pkgid=pkgid, yaml=filled,
                                   referer=request.referrer)
