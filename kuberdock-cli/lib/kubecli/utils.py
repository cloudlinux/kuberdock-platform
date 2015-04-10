import json
import logging
import requests

from requests.auth import HTTPBasicAuth

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


class kubeQuery(object):
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 15
    
    def _compose_args(self):
        args =  {
            'auth': HTTPBasicAuth(
                getattr(self, 'user', 'user'),
                getattr(self, 'password', 'password'))}
            #'timeout': (self.CONNECT_TIMEOUT, self.READ_TIMEOUT)}
        if self.url.startswith('https'):
            args['verify'] = False
        return args
    
    def _raise_error(self, error_string):
        if self.json:
            print json.dumps({'status': 'ERROR', 'message': error_string})
        else:
            print error_string
    
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
        try:
            req = requests.get(self._make_url(res), **args)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))
        return self._return_request(req)

    def post(self, res, data, rest=False):
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        try:
            req = requests.post(self._make_url(res), **args)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))
        return self._return_request(req)
    
    def put(self, res, data):
        args = self._compose_args()
        args['data'] = data
        args['headers'] = {'Content-type': 'application/json',
                           'Accept': 'text/plain'}
        try:
            req = requests.put(self._make_url(res), **args)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))
        return self._return_request(req)
    
    def delete(self, res):
        args = self._compose_args()
        try:
            req = requests.delete(self._make_url(res), **args)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))
        return self._return_request(req)
    
class PrintOut(object):
    WIDTH = 80
    HEADER = True
    DIVIDER = ','
    
    def _unwrap(self, data):
        try:
            return data['data']
        except (TypeError, KeyError):
            return data
    
    def out(self, data):
        if self.json:
            self._print_json(data)
        else:
            self._print_text(data)
            
    @staticmethod
    def _print_json(data):
        """
        Prints out JSON
        """
        try:
            print json.dumps(data)
        except (ValueError, TypeError):
            print data
            
    def _print_text(self, data):
        if isinstance(data, dict):
            self._print_data(data)
        elif isinstance(data, list):
            self._print_header(data)
            for item in data:
                self._print_data(item)
        else:
            raise SystemExit("Wrong format")
        
    def _print_header(self, data, width=None):
        """
        Prints list header getting first entry keys
        :param data: data to print out -- list
        :param width: field width -- integer
        """
        if not self.HEADER:
            return
        if not len(data):
            return
        try:
            fields = sorted(data[0].keys())
            if width is None:
                width = self.WIDTH
            if hasattr(self, 'fields'):
                fields = filter((lambda x: x in self.fields), fields)
            field_width = width / len(fields)
            fmt = self.DIVIDER.join([
                "{{{0}:^{1}}}".format(i, field_width)
                    for i in range(len(fields))])
            print fmt.format(*fields)
            print '-' * width
        except (AttributeError, ZeroDivisionError):
            return
        
    def _print_data(self, data, width=None):
        if width is None:
            width = self.WIDTH
        if hasattr(self, 'fields'):
            data = dict(filter((lambda x: x[0] in self.fields), data.items()))
        try:
            fields = sorted(data.keys())
            field_width = width / len(fields)
            fmt = self.DIVIDER.join([
                "{{{0}:^{1}}}".format(i, field_width)
                 for i in range(len(fields))])
            print fmt.format(*[data[f] for f in fields])
        except (AttributeError, ZeroDivisionError):
            return