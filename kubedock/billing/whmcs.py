import hashlib
import urlparse

from flask import request
from kubedock.utils import APIError
from kubedock.kapi.billing import BillingCommon


class BillingWHMCS(BillingCommon):
    def __init__(self):
        super(BillingWHMCS, self).__init__()

    def get_info(self, data):
        data['kdServer'] = self._get_master_url()
        try:
            result = self._query('getkuberdockinfo', data).get('results')
            return result
        except APIError, e:
            if e.message == 'User not found':
                raise APIError(self.url, type='Billing API error: User not found')
            else:
                raise e

    def get_payment_methods(self):
        return self._query('getpaymentmethods').get('paymentmethods').get('paymentmethod')

    def order_product(self, data, user=None):
        return self._query('orderkuberdockproduct', data).get('results')

    def order_pod(self, data, user=None):
        if user:
            data['client_id'] = user.clientid
        try:
            result = self._query('orderkuberdockpod', data).get('results')
            return result
        except Exception, e:
            raise APIError('Could not process billing response: '+str(e))

    def order_kubes(self, data, user=None):
        if user:
            data['client_id'] = user.clientid
        result = self._query('addkuberdockkubes', data).get('results')
        return result

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
