from kubedock.utils import APIError
from kubedock.kapi.billing import BillingCommon


class NoBillingError(APIError):
    message = 'Without billing'
    status_code = 404


class NoBilling(BillingCommon):
    def __init__(self):
        super(NoBilling, self).__init__()

    def get_info(self, data, user=None):
        raise NoBillingError()

    def order_product(self, data):
        raise NoBillingError()

    def get_payment_methods(self):
        raise NoBillingError()
