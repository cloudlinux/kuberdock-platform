from ..base import ClientBase


class AllowedPortsClient(ClientBase):
    endpoint = '/allowed-ports'

    def list(self):
        return self.transport.get(self._url())

    def open(self, port, protocol):
        json = {
            'port': port,
            'protocol': protocol,
        }
        return self.transport.post(self._url(), json=json)

    def close(self, port, protocol):
        return self.transport.delete(self._url(port, protocol))
