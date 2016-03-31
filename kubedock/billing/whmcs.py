import hashlib
import urlparse
from urllib import urlencode
from time import time

from flask import request
from kubedock.utils import APIError
from kubedock.kapi.billing import BillingCommon
from kubedock.system_settings.models import SystemSettings
from flask import current_app

STATUS_UNPAID = 'Unpaid'
STATUS_PENDING = 'Pending'


class BillingWHMCS(BillingCommon):
    def __init__(self):
        super(BillingWHMCS, self).__init__()

    def get_info(self, data, user=None):
        data['kdServer'] = self._get_master_url()
        try:
            return self._query('getkuberdockinfo', data).get('results')
        except APIError, e:
            if e.message == 'User not found':
                raise APIError(self.url, type='Billing API error: User not found')
            else:
                raise e

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

    def order_pod(self, data, user=None):
        if user:
            data['client_id'] = user.clientid
        try:
            result = self._query('orderkuberdockpod', data).get('results')
            if result['status'] == 'Unpaid':
                result['redirect'] = self.get_autologin_url(
                    user, 'viewinvoice.php?id={0}'.format(result['invoice_id']))
            return result
        except Exception, e:
            raise APIError('Could not process billing response: '+str(e))

    def order_kubes(self, data, user=None):
        if user:
            data['client_id'] = user.clientid
        result = self._query('addkuberdockkubes', data).get('results')
        if result['status'] == 'Unpaid':
            result['redirect'] = self.get_autologin_url(user, 'viewinvoice.php?id={0}'.format(result['invoice_id']))

        return result

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

    def get_autologin_url(self, user, goto):
        """
        Generate WHMCS AutoAuth link.
        http://docs.whmcs.com/AutoAuth

        :param user: User model
        :param goto: where to send the user after successful authentication.
        """
        whmcs_url = self._make_url('dologin.php')
        auth_key = SystemSettings.get_by_name('sso_secret_key')
        timestamp = str(int(time()))
        email = user.email
        auth_hash = hashlib.sha1(email + timestamp + auth_key).hexdigest()

        url = urlparse.urlparse(whmcs_url)
        query = urlencode(dict(urlparse.parse_qsl(url.query), email=email,
                               timestamp=timestamp, hash=auth_hash, goto=goto))
        return url._replace(query=query).geturl()

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
        args['headers'] = {
            'User-Agent': 'Mozilla/5.0'
        }
        res = self.run('post', '/includes/api.php', args)

        try:
            if 'result' in res and res['result'] == 'success':
                return res
            else:
                raise APIError(res['message'], type='Billing API error')
        except TypeError:
            raise APIError('Undefined response', type='Billing API error')
