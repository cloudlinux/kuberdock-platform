from kubedock.utils import APIError
from kubedock.kapi.billing import BillingCommon
from kubedock.kapi.users import UserCollection
from kubedock.billing.models import Package, Kube


class NoBillingError(APIError):
    message = 'Without billing'
    status_code = 404


class NoBilling(BillingCommon):
    def __init__(self):
        super(NoBilling, self).__init__()

    def get_info(self, data):
        response = {
            'billing': 'No billing',
            'packages': [p.to_dict(with_kubes=True) for p in Package.query.all()],
            'default': {
                'kubeType': Kube.get_default_kube().to_dict(),
                'packageId': Package.get_default().to_dict(),
            }
        }

        return response

    def order_product(self, data, user=None):
        raise NoBillingError()

    def order_pod(self, data, user=None):
        raise NoBillingError()

    def get_payment_methods(self):
        raise NoBillingError()
