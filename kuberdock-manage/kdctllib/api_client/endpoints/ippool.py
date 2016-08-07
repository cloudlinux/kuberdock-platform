from ..base import ClientBase


class IPPoolClient(ClientBase):
    endpoint = '/ippool'

    def list(self, page=None, free_only=False):
        params = {'page': page, 'free-only': free_only}

        return self.transport.get(
            self._url(),
            params=params
        )

    def get(self, network, page=None):
        params = {'page': page}

        return self.transport.get(
            self._url(network),
            params=params
        )

    def create(self, ippool_data):
        return self.transport.post(
            self._url(),
            json=ippool_data
        )

    def update(self, network, ippool_data):
        return self.transport.put(
            self._url(network),
            json=ippool_data
        )

    def delete(self, network):
        return self.transport.delete(
            self._url(network)
        )
