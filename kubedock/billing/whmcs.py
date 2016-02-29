import hashlib
import urlparse

from flask import request
from kubedock.utils import APIError
from kubedock.kapi.billing import BillingCommon
from flask import current_app

STATUS_UNPAID = 'Unpaid'
STATUS_PENDING = 'Pending'


class BillingWHMCS(BillingCommon):
    def __init__(self):
        super(BillingWHMCS, self).__init__()

    def get_info(self, data, user=None):
        if user is not None and user.username == 'hostingPanel':
            raise APIError(self.url, type='Billing API error')
        data['kdServer'] = self._get_master_url()
        return self._query('getkuberdockinfo', data).get('results')

    def get_payment_methods(self):
        return self._query('getpaymentmethods').get('paymentmethods').get('paymentmethod')

    def order_product(self, data):
        info = self.get_info(data)
        # TODO in WHMCS: info['userServices'] must return only one service
        if info['userServices']:
            index = list(info['userServices']).pop()
            service = info['userServices'][index]
        else:
            service = None

        if service is None:
            order = self.add_order(info, data)
            order_id = order['orderid']
            service_id = order['productids']
        elif service['domainstatus'] == STATUS_PENDING:
            order = self.get_order(service['orderid'])
            order_id = order['id']
            service_id = service['id']
        else:
            order = None

        if order:
            if int(order['invoiceid']) > 0:
                invoice = self.get_invoice(order['invoiceid'])
                if invoice['status'] == STATUS_UNPAID:
                    raise APIError('You have no enough funds. '
                                   'Please make payment in billing system at {0}'.format(self.url))
            self.accept_order(order_id, auto_setup=False)
            self.module_create(service_id)

        return self.get_info(data).get('userServices')

    def add_order(self, info, data):
        package_id = data.get('package_id', None)
        price = data.get('price', None)
        payment_method = data.get('payment_method', None)
        self._get_package_by_id(info, package_id)
        if not payment_method and info['userDetails']['defaultgateway']:
            payment_method = info['userDetails']['defaultgateway']

        data = {
            'clientid': info['userDetails']['id'],
            'pid': package_id,
            'paymentmethod': payment_method,
            'billingcycle': data.get('billing_cycle', 'free'),
        }
        if price:
            data['priceoverride'] = price

        return self._query('addorder', data)

    def get_order(self, order_id):
        return self._query('getorders', {'id': order_id}).get('orders').get('order')[0]

    def accept_order(self, order_id, auto_setup=True, send_email=1):
        data = {
            'orderid': order_id,
            'autosetup': auto_setup,
            'sendemail': send_email,
        }
        return self._query('acceptorder', data)

    def module_create(self, account_id):
        return self._query('modulecreate', {'accountid': account_id})

    def get_invoice(self, invoice_id):
        return self._query('getinvoice', {'invoiceid': invoice_id})

    def _get_package_by_id(self, info, package_id):
        try:
            return (p for p in info.get('products', {}) if p['id'] == package_id).next()
        except StopIteration:
            raise APIError('Product with id {0} not found'.format(package_id))

    def _get_master_url(self):
        url = urlparse.urlparse(request.url_root)
        return '{0}://{1}'.format(url.scheme, url.netloc)

    def _query(self, action, data=None):
        m = hashlib.md5()
        m.update(self.password)
        args = dict()
        args['data'] = {
            'action': action,
            'username': self.username,
            'password': m.hexdigest(),
            'responsetype': 'json',
        }
        if data:
            args['data'].update(data)
        res = self.run('post', '/includes/api.php', args)

        try:
            if 'result' in res and res['result'] == 'success':
                return res
            else:
                raise APIError(self.url, type='Billing API error')
        except TypeError:
            raise APIError('Undefined response', type='Billing API error')
