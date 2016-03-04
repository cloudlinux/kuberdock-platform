from kubedock.utils import APIError
from kubedock.kapi.billing import BillingCommon
from kubedock.kapi.users import UserCollection
from kubedock.billing.models import Package, Kube, PackageKube


class NoBillingError(APIError):
    message = 'Without billing'
    status_code = 404


class NoBilling(BillingCommon):
    def __init__(self):
        super(NoBilling, self).__init__()

    def get_info(self, data, user=None):
        user_data = UserCollection().get(user=user.id)
        package_data = Package().by_name(user_data['package'])

        response = {
            'billing': 'No billing',
            'user': user_data,
            'package': package_data.to_dict(with_kubes=True) if package_data else {},
            'default': {
                'kubeType': Kube.get_default_kube().to_dict(),
                'packageId': Package.get_default().to_dict(),
            }
        }

        if user.role.rolename == 'HostingPanel':
            response['packages'] = [p.to_dict(with_kubes=True) for p in Package.query.all()]

        return response

    def order_product(self, data):
        raise NoBillingError()

    def order_pod(self, data, user=None):
        raise NoBillingError()

    def get_payment_methods(self):
        raise NoBillingError()
