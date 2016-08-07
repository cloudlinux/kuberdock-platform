class ClientBase(object):
    endpoint = '/'

    def __init__(self, client):
        self.client = client
        self.endpoint = client.endpoint + self.endpoint

    @property
    def transport(self):
        """:rtype: :class:`transport.Transport`"""
        return self.client.transport

    def _url(self, *parts):
        rv = self.endpoint
        for p in filter(None, parts):
            rv += '/' + str(p)
        return rv
