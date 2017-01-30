
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import copy
from functools import wraps

from flask import Blueprint, current_app, request

from kubedock.core import db
from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError, BillingExc, NoFreeIPs, \
    NoFreeIPsAdminNotification
from kubedock.login import auth_required
from kubedock.utils import atomic, KubeUtils
from kubedock.billing.models import Package, Kube
from kubedock.system_settings.models import SystemSettings
from kubedock.kapi.apps import PredefinedApp, AppInstance, start_pod_from_yaml
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


@billing.route('/info', methods=['GET'])
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing(raise_=False)
def get_billing_info(billing_driver):
    data = KubeUtils._get_params()
    if billing_driver is None:
        return no_billing_data()
    return billing_driver.getkuberdockinfo(**data)


@billing.route('/paymentmethods', methods=['GET'])
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def payment_methods(billing_driver):
    return billing_driver.getpaymentmethods()


@billing.route('/order', methods=['POST'])
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


@billing.route('/orderPodEdit', methods=['POST'])
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def order_edit(billing_driver):
    data = KubeUtils._get_params()

    owner = KubeUtils.get_current_user()
    pod_collection = PodCollection(owner)
    pod = data['pod']
    pod_id = pod['id']
    old_pod = pod_collection._get_by_id(pod_id)
    new_config = copy.deepcopy(pod.get('edited_config'))
    try:
        pod_collection._preprocess_public_access(new_config)
        pod_collection._preprocess_new_pod(new_config, original_pod=old_pod)
    except NoFreeIPs:
        raise NoFreeIPsAdminNotification(
            response_message='There is a problem with a package you trying '
                             'to buy. Please, try again or contact support '
                             'team.')

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
               methods=['POST'])
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def switch_app_package(billing_driver, pod_id, plan_id):
    owner = KubeUtils.get_current_user()

    transaction = db.session.begin_nested()
    with atomic():
        old_pod = PodCollection(owner).get(pod_id, as_json=True)
        AppInstance(pod_id).update_plan(plan_id, async=False, dry_run=True)
        pod = PodCollection(owner).get(pod_id, as_json=True)
    transaction.rollback()

    data = KubeUtils._get_params()
    data['pod'] = pod
    data['oldPod'] = old_pod
    data['referer'] = data.get('referer') or ''
    return billing_driver.orderswitchapppackage(**data)


@billing.route('/orderKubes', methods=['POST'])
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def order_kubes(billing_driver):
    data = KubeUtils._get_params()
    data['referer'] = data['referer'] if 'referer' in data else ''
    return billing_driver.orderkubes(**data)


@billing.route('/orderapp/<int:template_id>/<int:plan_id>',
               methods=['POST'])
# Currently this workflow does not imply authentication but we can force it
# @auth_required
@maintenance_protected
@KubeUtils.jsonwrap
@with_billing()
def order_app(billing_driver, template_id, plan_id):
    data = KubeUtils._get_params()
    app = PredefinedApp.get(template_id)

    try:
        start_pod_from_yaml(app.get_filled_template_for_plan(plan_id, data),
                            dry_run=True)
    except NoFreeIPs:
        raise NoFreeIPsAdminNotification(
            response_message='There is a problem with a package you trying '
                             'to buy. Please, try again or contact support '
                             'team.')

    filled = app.get_filled_template_for_plan(plan_id, data, as_yaml=True)
    pkgid = app._get_package().id

    return billing_driver.orderapp(pkgid=pkgid, yaml=filled,
                                   referer=request.referrer)
