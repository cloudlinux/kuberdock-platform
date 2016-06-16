import requests

from .exceptions import APIError


def _get_response_message(response):
    try:
        return response.json()
    except ValueError:
        return response.text


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

    def request(self, method, url, **kwargs):
        url = self.url + url
        response = self.conn.request(method, url, **kwargs)

        if response.ok:
            return _get_response_message(response)
        else:
            raise APIError(_get_response_message(response))

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
