import ConfigParser
import collections
import hashlib
import json
import logging
import operator
import os
import stat
import warnings
from functools import wraps

import click
import requests
from requests.auth import HTTPBasicAuth

GLOBAL_CONFIG = '/etc/kubecli.conf'

logging.basicConfig()
requests_logger = logging.getLogger('requests_logger')


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


class KubeQuery(object):
    """Class implements a set of requests to kuberdock API"""
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 15

    def __init__(self, url='', user='user', password='passwrod',
                 token=None, jsonify_errors=False, **kwargs):
        """
        :param url: Base URL of kuberdock API server
        :param user: user for HTTP Authentication in API calls
        :param password: password for HTTP Authentication in API calls
        :param token: optional token for API calls
        :param jsonify_errors: print out errors messages as json string
        """
        self.user = user
        self.url = url
        self.password = password
        self.jsonify_errors = jsonify_errors
        self.token = token
        self.conn = requests.Session()
        self.conn.verify = False
        self.request_logger = RequestsLogger(self.conn, requests_logger)
        if kwargs.get('debug', False):
            requests_logger.setLevel(logging.DEBUG)

    def _compose_args(self):
        args = {}
        if not self.token or self.token == 'None':
            args['auth'] = HTTPBasicAuth(self.user, self.password)
        return args

    def _raise_error(self, error_string):
        if self.jsonify_errors:
            raise SystemExit(
                json.dumps({'status': 'ERROR', 'message': error_string}))
        else:
            raise SystemExit(error_string)

    def _make_url(self, res):
        token = self.token
        token = '?token=%s' % token if token is not None else ''
        if res is not None:
            return self.url + res + token
        return self.url + token

    def _return_request(self, req):
        try:
            # handle errors returned in response status code
            req.raise_for_status()
            return req.json()
        except (ValueError, TypeError):
            return req.text

    def get(self, res=None, params=None):
        """Performs GET query to resource specified in 'res' argument.
        :param res: resource to GET request (/some/api/to/request)
        :param params: optional parameters
        """
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args)

    def post(self, res, data, rest=False):
        """Performs POST query to resource specified in 'res' argument.
        :param res: resource to POST request
        :param data: optional post data
        :param rest: ???
        """
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        return self._run('post', res, args)

    def put(self, res, data, rest=False):
        """Performs PUT query to resource specified in 'res' argument
        :param res: resource to PUT request
        :param data: optional PUT data
        """
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        return self._run('put', res, args)

    def delete(self, res):
        """Performs DELETE query to resource specified in 'res' argument
        :param res: resource to PUT request
        """
        args = self._compose_args()
        return self._run('delete', res, args)

    def _run(self, act, res, args):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                url = self._make_url(res)
                request_object = requests.Request(method=act, url=url, **args)
                request_object = self.conn.prepare_request(request_object)
                self.request_logger.log_curl_request(request_object)
                req = self.conn.send(request_object)
                self.request_logger.log_http_response(req)
                return self._return_request(req)
        except requests.exceptions.ConnectionError as e:
            return self._raise_error(str(e))
        except requests.exceptions.HTTPError as e:
            try:
                res = req.json()
                res = res['data']
            except:
                res = str(e)
            return self._raise_error(res)

    @staticmethod
    def unwrap(data):
        """Unwraps data from api response."""
        try:
            return data['data']
        except KeyError:
            return data


class PrintOut(object):
    """Helper class for pretty formatting of output."""

    def __init__(self, wants_header=False,
                 fields=(('name', 32),),
                 indent=4,
                 as_json=False):
        self.wants_header = wants_header
        if fields is None:
            self.fields = None
        else:
            self.fields = [(_u(f_name), f_len) for f_name, f_len in fields]
        self.indent = indent
        self.as_json = as_json
        PrintOut.instantiated = True

    def show_list(self, data):
        if self.as_json:
            self._print_json(data)
        else:
            self._print(data)

    def show(self, data):
        if self.as_json:
            self._print_json(data)
        else:
            self._r_print(data)

    @staticmethod
    def _print_json(data):
        try:
            click.echo(json.dumps(data, ensure_ascii=False))
        except (ValueError, TypeError):
            click.echo(json.dumps(
                {'status': 'ERROR', 'message': 'Unparseable format'}))

    def _print(self, data):
        if isinstance(data, collections.Mapping):
            self._list_data(data)
        elif isinstance(data, collections.Iterable):
            if self.wants_header:
                self._print_header()
            for item in data:
                self._list_data(item)
        else:
            raise SystemExit("Unknown format")

    def _r_print(self, data, offset=0):
        indent = u' ' * (self.indent * offset)
        if isinstance(data, dict):
            for k, v in sorted(data.items(), key=operator.itemgetter(0)):
                if isinstance(v, (list, dict)):
                    click.echo(u'{0}{1}:'.format(indent, _u(k)))
                    self._r_print(v, offset + 1)
                else:
                    click.echo(u'{0}{1}: {2}'.format(indent, _u(k), _u(v)))
        elif isinstance(data, list):
            for item in data:
                self._r_print(item, offset)
        elif isinstance(data, basestring):
            click.echo(u'{0}{1}'.format(indent, _u(data)))
        else:
            raise SystemExit("Unknown format")

    def _print_header(self):
        fmt = u''.join([u'{{{0}:<{1[1]}}}'.format(i, v)
                        for i, v in enumerate(self.fields)])
        click.echo(fmt.format(
            *[i[0].upper().replace('_', ' ') for i in self.fields]))

    def _list_data(self, data):
        if self.fields is None:
            self.fields = [(_u(k), 32) for k, v in data.items()]
        fmt = u''.join(
            [u'{{{0[0]}:<{0[1]}.{0[1]}}}'.format(i) for i in self.fields])
        try:
            click.echo(fmt.format(**{k: _u(v) for k, v in data.items()}))
        except ValueError:
            fmt = u''.join(
                [u'{{{0[0]}:<{0[1]}}}'.format(i) for i in self.fields])
            click.echo(fmt.format(**{k: _u(v) for k, v in data.items()}))


class RequestsLogger(object):
    def __init__(self, session, logger):
        self.session = session
        self.logger = logger
        if logger.level > logging.DEBUG:
            def _do_nothing(*args, **kwargs):
                pass

            self.log_curl_request = _do_nothing
            self.log_http_response = _do_nothing
            self.req = _do_nothing
            self.end = _do_nothing

    def log_curl_request(self, request):
        self.logger.debug('#################### Request ####################')
        curl = ['curl -i -L -X %s' % request.method]

        for (key, value) in request.headers.items():
            header = '-H \'%s: %s\'' % self._process_header(key, value)
            curl.append(header)

        if not self.session.verify:
            curl.append('-k')
        elif isinstance(self.session.verify, basestring):
            curl.append('--cacert %s' % self.session.verify)

        if self.session.cert:
            curl.append('--cert %s' % self.session.cert[0])
            curl.append('--key %s' % self.session.cert[1])

        if request.body:
            curl.append('-d \'%s\'' % request.body)

        curl.append('"%s"' % request.url)
        self.logger.debug(' '.join(curl))

    def log_http_response(self, resp):
        self.logger.debug('#################### Response ###################')
        status = (resp.raw.version / 10.0, resp.status_code, resp.reason)
        dump = ['\nHTTP/%.1f %s %s' % status]
        dump.extend(['%s: %s' % (k, v) for k, v in resp.headers.items()])
        dump.append('')
        dump.extend([resp.text, ''])
        self.logger.debug('\n'.join(dump))
        self.logger.debug('###################### End ######################')

    @staticmethod
    def _process_header(name, value):
        if name in ('X-Auth-Token',):
            v = value.encode('utf-8')
            h = hashlib.sha1(v)
            d = h.hexdigest()
            return name, "{SHA1}%s" % d
        else:
            return name, value


def make_config(args):
    create_user_config(args)
    excludes = ['call']
    config = parse_config(GLOBAL_CONFIG)
    config.update(parse_config(os.path.expanduser(args.config)))
    for k, v in vars(args).items():
        if k in excludes:
            continue
        if v is not None:
            config[k] = v
    return config


def parse_config(path):
    data = {}
    conf = ConfigParser.ConfigParser()
    conf.optionxform = str
    try:
        configs = conf.read(path)
    except ConfigParser.MissingSectionHeaderError as e:
        raise SystemExit(
            "Parsing error: missing section header in INI file. {0}".format(
                str(e)))
    except ConfigParser.DuplicateSectionError as e:
        raise SystemExit(
            "Parsing error: duplicate section header. {0}".format(str(e)))
    except ConfigParser.ParsingError as e:
        raise SystemExit("Parsing error: common error. {0}".format(str(e)))
    except IOError as e:
        raise SystemExit("Parsing error: I/O common error. {0}".format(str(e)))
    if len(configs) == 0:  # no configs found
        raise SystemExit(
            "Config '{0}' not found. Try to specify a "
            "custom one with option '--config'".format(
                path))
    for section in conf.sections():
        data.update(dict(conf.items(section)))
    return data


def create_user_config(args):
    default_path = os.path.expanduser(args.config)

    if not os.path.exists(default_path):
        with open(default_path, 'wb') as config:
            config.write('[defaults]\n'
                         'user = <YOUR USERNAME HERE>\n'
                         'password = <YOUR PASSWORD HERE>\n')
        os.chmod(default_path, stat.S_IRUSR | stat.S_IWUSR)


def echo(func):
    """
    Decorator that checks if PrintOut class has been already instantiated
    If no and output set to JSON --> print out a dumb message like
    {"status": "OK"}
    """

    @wraps(func)
    def inner(*args, **kw):
        func(*args, **kw)
        if getattr(args[0], 'as_json', False):
            if not getattr(PrintOut, 'instantiated', False):
                click.echo(json.dumps({'status': 'OK'}))

    return inner


def _u(s):
    """Convert any string to unicode"""
    if isinstance(s, unicode):
        return s
    elif isinstance(s, str):
        return s.decode('utf-8')
    else:
        return unicode(s)
