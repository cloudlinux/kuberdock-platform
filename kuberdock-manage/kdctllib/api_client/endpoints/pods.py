from ..base import ClientBase


class PodsClient(ClientBase):
    endpoint = '/podapi'

    def list(self, owner=None):
        return self.transport.get(
            self._url(),
            params={'owner': owner}
        )

    def get(self, id, owner=None):
        return self.transport.get(
            self._url(id),
            params={'owner': owner}
        )

    def create(self, data, owner=None):
        return self.transport.post(
            self._url(),
            params={'owner': owner},
            json=data
        )

    def update(self, id, data):
        # todo: add parameter "owner" in api/v2
        return self.transport.put(
            self._url(id),
            json=data
        )

    def delete(self, id, owner=None):
        return self.transport.delete(
            self._url(id),
            params={'owner': owner}
        )
