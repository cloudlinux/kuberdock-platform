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
        rv = (self.endpoint + ''.join('/' + str(p)
                                      for p in parts
                                      if p is not None))
        return rv
