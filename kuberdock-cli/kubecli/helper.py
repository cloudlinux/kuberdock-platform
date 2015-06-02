import json
import logging
import operator
import requests
import ConfigParser
import collections
import warnings

from requests.auth import HTTPBasicAuth


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


class KubeQuery(object):
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
            raise SystemExit(json.dumps({'status': 'ERROR', 'message': error_string}))
        else:
            raise SystemExit(error_string)

    def _make_url(self, res):
        if res is not None:
            return self.url + res
        return self.url

    def _return_request(self, req):
        try:
            return req.json()
        except (ValueError, TypeError):
            return req.text

    def _get(self, res=None, params=None):
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args)

    def _post(self, res, data, rest=False):
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        return self._run('post', res, args)

    def _put(self, res, data):
        args = self._compose_args()
        args['data'] = data
        args['headers'] = {'Content-type': 'application/json',
                           'Accept': 'text/plain'}
        return self._run('put', res, args)

    def _del(self, res):
        args = self._compose_args()
        return self._run('del', res, args)

    def _run(self, act, res, args):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete
        }
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                req = dispatcher.get(act, 'get')(self._make_url(res), **args)
                return self._return_request(req)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))


class PrintOut(object):

    def _check_defaults(self):
        if getattr(self, '_WANTS_HEADER', None) is None:
            self._WANTS_HEADER = False
        if getattr(self, '_FIELDS', None) is None:
            self._FIELDS = (('name', 32),)
        if getattr(self, '_INDENT', None) is None:
            self._INDENT = 4

    def _list(self, data):
        self._check_defaults()
        if self.json:
            self._print_json(data)
        else:
            self._print(data)

    def _show(self, data):
        self._check_defaults()
        if self.json:
            self._print_json(data)
        else:
            self._r_print(data)

    @staticmethod
    def _print_json(data):
        try:
            print json.dumps(data)
        except (ValueError, TypeError):
            print json.dumps({'status': 'ERROR', 'message': 'Unparseable format'})

    def _print(self, data):
        if isinstance(data, collections.Mapping):
            self._list_data(data)
        elif isinstance(data, collections.Iterable):
            if self._WANTS_HEADER:
                self._print_header()
            for item in data:
                self._list_data(item)
        else:
            raise SystemExit("Unknown format")

    def _r_print(self, data, offset=0):
        if isinstance(data, dict):
            for k, v in sorted(data.items(), key=operator.itemgetter(0)):
                if isinstance(v, (list, dict)):
                    print "{0}{1}:".format(' ' * (self._INDENT * offset), k)
                    self._r_print(v, offset+1)
                else:
                    print '{0}{1}: {2}'.format(
                        ' ' * (self._INDENT * offset), k, v)
        elif isinstance(data, list):
            for item in data:
                self._r_print(item, offset)
        else:
            raise SystemExit("Unknown format")

    def _print_header(self):
        fmt = ''.join( ['{{{0}:<{1[1]}}}'.format(i, v)
                for i, v in enumerate(self._FIELDS)])
        print fmt.format(*[i[0].upper() for i in self._FIELDS])

    def _list_data(self, data):
        fmt = ''.join(['{{{0[0]}:<{0[1]}}}'.format(i) for i in self._FIELDS])
        print fmt.format(**data)

    @staticmethod
    def _unwrap(data):
        try:
            return data['data']
        except KeyError:
            return data


def make_config(args):
    excludes = ['call', 'config']
    config = parse_config(args.config)
    for  k, v in vars(args).items():
        if k in excludes:
            continue
        if v is not None:
            config[k] = v
    return config

def parse_config(path):
    data = {}
    conf = ConfigParser.ConfigParser()
    conf.optionxform = str
    configs = conf.read(path)
    if len(configs) == 0:   # no configs found
        raise SystemExit(
            "Config '{0}' not found. Try to specify a custom one with option '--config'".format(path))
    for section in conf.sections():
        data.update(dict(conf.items(section)))
    return data