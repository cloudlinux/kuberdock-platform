from ..base import ClientBase


class PStorageClient(ClientBase):
    endpoint = '/pstorage'

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

    # Server does not support edit method

    def delete(self, id, owner=None):
        return self.transport.delete(
            self._url(id),
            params={'owner': owner}
        )
