import requests

from .exceptions import APIError


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

    def request(self, method, url, params=None, data=None, **kwargs):
        url = self.url + url
        response = self.conn.request(method, url, params, data, **kwargs)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise APIError(e.message)
        else:
            try:
                return response.json()
            except ValueError:
                return response.text

    def get(self, url, params=None):
        return self.request('GET', url, params)

    def post(self, url, params=None, data=None):
        return self.request(
            'POST', url, params, data,
        )

    def put(self, url, params=None, data=None):
        return self.request(
            'PUT', url, params, data,
        )

    def delete(self, url, params=None):
        return self.request('DELETE', url, params)
