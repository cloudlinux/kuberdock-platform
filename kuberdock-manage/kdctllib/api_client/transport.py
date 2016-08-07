import requests
from exceptions import APIError, UnknownAnswer
from utils import RequestsLogger


class Transport(object):
    def __init__(self, url, user=None, password=None, token=None):
        conn = requests.Session()
        if user:
            conn.auth = (user, password)
        conn.verify = False
        if token:
            conn.params.update(token=token)
        self._token = token
        self.conn = conn
        self.url = url
        self.requests_logger = RequestsLogger(conn)

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, value):
        self.conn.params.update(token=value)
        self._token = value

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

    def request(self, method, url, **kwargs):
        url = self.url + url

        r = requests.Request(method=method, url=url, **kwargs)
        r = self.conn.prepare_request(r)
        self.requests_logger.log_curl_request(r)

        response = self.conn.send(r)
        rv = self._unwrap_response(response)
        return rv

    @staticmethod
    def _unwrap_response(response):
        try:
            d = response.json()
        except ValueError:
            raise UnknownAnswer(response.text, response.status_code)
        if response.ok:
            return d
        else:
            raise APIError(d)
