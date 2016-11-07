import hashlib
import operator
import os
import sys
from urlparse import urlparse

import requests
import yaml
from requests.auth import HTTPBasicAuth

from flask import request
from kubedock.exceptions import BillingExc
from kubedock.system_settings.models import SystemSettings
from kubedock.utils import KubeUtils


class BillingFactory(object):

    PLUGIN_FOLDER_NAME = 'plugins'

    def __init__(self, plugin_dir=None):
        self.plugin_dir = plugin_dir
        if self.plugin_dir is None:
            self.plugin_dir = os.path.join(
                os.path.dirname(__file__),
                self.PLUGIN_FOLDER_NAME)

    def init_app(self, app):
        app.billing_factory = self

    def _get_billing_plugins(self):
        data = {}
        if not os.path.isdir(self.plugin_dir):
            return data
        for item in os.listdir(self.plugin_dir):
            if not item.endswith('.yml') and not item.endswith('.yaml'):
                continue
            with open(os.path.join(self.plugin_dir, item)) as f:
                item_data = yaml.safe_load(f.read())
            item_name = item_data.pop('name', None)
            if item_name is None:
                continue
            data[item_name] = item_data
        return data

    def get_billing(self, name):
        if not hasattr(self, '_plugins'):
            self._plugins = self._get_billing_plugins()
        if name not in self._plugins:
            raise KeyError('No such billing: {0}'.format(name))
        return Billing(self._plugins[name])

    def list_billing_plugins(self):
        if not hasattr(self, '_plugins'):
            self._plugins = self._get_billing_plugins()
        return sorted(self._plugins.keys())

    def update_billing_plugins(self):
        self._plugins = self._get_billing_plugins()

    def _get_custom_value(self, name, key):
        if not hasattr(self, '_plugins'):
            self._plugins = self._get_billing_plugins()
        data = self._plugins.get(name, {}).get(key)
        return data if data is not None else ''

    def get_pod_url(self, name):
        return self._get_custom_value(name, 'pod-url')

    def get_app_url(self, name):
        return self._get_custom_value(name, 'app-url')


class Billing(object):

    def __init__(self, data):
        self._structure = data
        self._dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'delete': requests.delete}

        self._get_system_settings()

        dgst = data.get('password-digest')
        if (dgst is not None and isinstance(dgst, basestring) and
                hasattr(hashlib, dgst.lower())):
            m = operator.methodcaller(dgst.lower(),
                                      self.billing_password)(hashlib)
            self.billing_password = m.hexdigest()

        _url = urlparse(request.base_url)
        self.master_url = '{0}://{1}'.format(_url.scheme, _url.netloc)

    def _get_system_settings(self):
        settings_list = SystemSettings.get_all()
        wanted_names = ['billing_url', 'billing_username', 'billing_password']
        for i in settings_list:
            if i.get('name') in wanted_names:
                super(Billing, self).__setattr__(
                    i.get('name'), i.get('value'))

    def _compose_url(self, endpoint):
        url = '/'.join([
            self.billing_url.rstrip('/'),
            endpoint.lstrip('/')])
        if not urlparse(url).scheme:
            url = 'http://{0}'.format(url)
        return url

    def _compose_args(self, method, data=None):
        args = {}
        if data is None:
            data = {}
        query = 'params' if method == 'get' else 'data'
        args[query] = self._structure.get('common-params', {})
        args[query].update(data)
        args['headers'] = self._structure.get('common-headers', {})
        auth = self._structure.get('auth')
        if auth == 'params':
            args[query].update({'username': self.billing_username,
                                'password': self.billing_password})
        elif auth == 'headers':
            args['auth'] = HTTPBasicAuth(
                self.billing_username, self.billing_password)
        return args

    @staticmethod
    def _get_return_value(data, rv):
        ret = data.get('return')
        if ret:
            composed_ret = rv
            for key in ret:
                try:
                    composed_ret = composed_ret[key]
                except (KeyError, IndexError, TypeError):
                    return composed_ret
            return composed_ret
        return rv

    def _check_for_errors(self, data):
        resp = self._structure.get('response')
        if resp is None or resp.get('status') is None:
            return data
        if not isinstance(resp['status'], dict):
            return data
        status = resp['status']
        key, success, error = map(status.get, ('key', 'success', 'error'))
        if key is None:
            return data
        result = data.get(key)
        if result == error or result != success:
            if 'error-message' in resp and resp['error-message'] in data:
                raise BillingExc.BillingError(data[resp['error-message']])
            raise BillingExc.BillingError
        return data

    def _fill_params(self, params, kw):
        _data = {}
        for key, value in params.items():
            if value is None:
                if key == 'kdServer':
                    _data['kdServer'] = self.master_url
                elif key == 'client_id':
                    current_user = KubeUtils.get_current_user()
                    _data['client_id'] = getattr(
                        current_user, 'clientid', None)
            else:
                _data[key] = kw.get(value) if value in kw else value
        return _data

    def _make_method(self, data):
        def method(*args, **kw):
            m = data.get('method', 'get')
            f = self._dispatcher.get(m)
            url = self._compose_url(data.get('endpoint', ''))
            params = data.get('params', {})
            expected_args = data.get('args', [])    # list
            prepared_args = dict(zip(expected_args, args))  # dict
            prepared_args.update(kw)
            if set(expected_args) - set(prepared_args.keys()):
                raise TypeError('Improper number of arguments')
            filled_params = self._fill_params(params, prepared_args)
            request_args = self._compose_args(m, filled_params)
            try:
                r = f(url, **request_args)
                try:
                    rv = r.json()
                except ValueError:
                    return r.text
            except Exception:
                raise BillingExc.InternalBillingError.from_exc(*sys.exc_info())
            return self._get_return_value(data, self._check_for_errors(rv))
        return method

    def __getattr__(self, name):
        if name in self._structure.get('methods'):
            data = self._structure['methods'][name]
            return self._make_method(data)
        raise AttributeError('No such attribute: {0}'.format(name))
