from abc import ABCMeta, abstractmethod

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError, ConnectionError, MissingSchema

from kubedock.system_settings.models import SystemSettings
from kubedock.exceptions import APIError


class BillingCommon(object):
    RETURN_JSON = True

    __metaclass__ = ABCMeta

    def __init__(self):
        self.url = SystemSettings.get_by_name('billing_url')
        self.username = SystemSettings.get_by_name('billing_username')
        self.password = SystemSettings.get_by_name('billing_password')

    @abstractmethod
    def get_info(self, data):
        return

    @abstractmethod
    def order_product(self, data, user=None):
        return

    @abstractmethod
    def order_pod(self, data, user=None):
        return

    @abstractmethod
    def get_payment_methods(self):
        return

    def _compose_args(self):
        args = dict()
        args['auth'] = HTTPBasicAuth(self.username, self.password)
        if self.url.startswith('https'):
            args['verify'] = False
        return args

    def _raise_error(self, error_string):
        if self.RETURN_JSON:
            raise APIError(error_string)
        else:
            raise SystemExit(error_string)

    def _make_url(self, res):
        if res is not None:
            if not self.url.endswith('/') and not res.startswith('/'):
                res = '/' + res
            return self.url + res
        return self.url

    def _return_request(self, req):
        try:
            req.raise_for_status()
            return req.json()
        except (ValueError, TypeError):
            return req.text
        except HTTPError, e:
            try:
                return req.json()
            except e:
                return str(req)

    def get(self, res=None, params=None):
        """Performs GET query to resource specified in 'res' argument."""
        args = self._compose_args()
        if params:
            args['params'] = params
        return self.run('get', res, args)

    def post(self, res, data, rest=False):
        """Performs POST query to resource specified in 'res' argument."""
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        return self.run('post', res, args)

    def put(self, res, data, rest=False):
        """Performs PUT query to resource specified in 'res' argument"""
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        return self.run('put', res, args)

    def delete(self, res):
        """Performs DELETE query to resource specified in 'res' argument"""
        args = self._compose_args()
        return self.run('del', res, args)

    def run(self, act, res, args):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete
        }

        try:
            req = dispatcher.get(act, requests.get)(self._make_url(res),
                                                    **args)
            return self._return_request(req)
        except (ConnectionError, MissingSchema) as e:
            return self._raise_error(str(e))
