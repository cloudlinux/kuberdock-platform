import hashlib
import logging

import requests

from .exceptions import APIError

requests_logger = logging.getLogger('requests_logger')


def _get_response_message(response):
    try:
        return response.json()
    except ValueError:
        return response.text


def _raise(response_message):
    if isinstance(response_message, dict):
        raise APIError(response_message.get('data'),
                       response_message.get('type'),
                       response_message.get('details'))
    else:
        raise APIError(response_message)


class ClientBase(object):
    endpoint = '/'

    def __init__(self, client):
        self.client = client
        self.endpoint = client.endpoint + self.endpoint

    @property
    def transport(self):
        return self.client.transport

    def _url(self, *parts):
        return self.endpoint + '/' + '/'.join(str(part) for part in parts)


class Transport(object):
    def __init__(self, url, user=None, password=None, token=None):
        conn = requests.Session()
        if user:
            conn.auth = (user, password)
        conn.verify = False
        if token:
            conn.params.update(
                {'token': token}
            )
        self.conn = conn
        self.url = url
        self.requests_logger = RequestsLogger(conn, requests_logger)

    def request(self, method, url, **kwargs):
        url = self.url + url

        r = requests.Request(method=method, url=url, **kwargs)
        r = self.conn.prepare_request(r)
        self.requests_logger.log_curl_request(r)

        response = self.conn.send(r)
        self.requests_logger.log_http_response(response)

        response_message = _get_response_message(response)
        if response.ok:
            return response_message
        else:
            _raise(response_message)

    def get(self, url, params=None):
        return self.request('GET', url, params=params)

    def post(self, url, params=None, json=None, **kwargs):
        return self.request(
            'POST', url, params=params, json=json, **kwargs
        )

    def put(self, url, params=None, json=None, **kwargs):
        return self.request(
            'PUT', url, params=params, json=json, **kwargs
        )

    def delete(self, url, params=None, json=None, **kwargs):
        return self.request(
            'DELETE', url, params=params, json=json, **kwargs
        )


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
