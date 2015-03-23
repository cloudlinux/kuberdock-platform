import requests
from requests.auth import HTTPBasicAuth


class kubeQuery(object):
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 15
    
    def _compose_args(self):
        return {
            'auth': HTTPBasicAuth(self.user, self.passwd),
            'timeout': (self.CONNECT_TIMEOUT, self.READ_TIMEOUT)}
    
    def _make_url(self, res):
        if res is not None:
            return self.url + res
        return self.url
    
    def _return_request(self, req):
        try:
            return req.json()
        except (ValueError, TypeError):
            return req.text
    
    def get(self, res=None, params=None):
        args = self._compose_args()
        if params:
            args['params'] = params
        req = requests.get(self._make_url(res), **args)
        return self._return_request(req)

    def post(self, res, data, rest=False):
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        req = requests.post(self._make_url(res), **args)
        return self._return_request(req)
    
    def put(self, res, data):
        args = self._compose_args()
        args['data'] = data
        args['headers'] = {'Content-type': 'application/json',
                           'Accept': 'text/plain'}
        req = requests.put(self._make_url(res), **args)
        return self._return_request(req)
    
    def delete(self, res):
        args = self._compose_args()
        req = requests.delete(self._make_url(res), **args)
        return self._return_request(req)
