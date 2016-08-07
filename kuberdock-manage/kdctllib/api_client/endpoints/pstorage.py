from ..base import ClientBase


class PStorageClient(ClientBase):
    endpoint = '/pstorage'

    def list(self, owner=None):
        return self.transport.get(
            self._url(),
            params={'owner': owner}
        )

    def get(self, device_id, owner=None):
        return self.transport.get(
            self._url(device_id),
            params={'owner': owner}
        )

    def create(self, device_data, owner=None):
        return self.transport.post(
            self._url(),
            params={'owner': owner},
            json=device_data
        )

    # Server does not support edit method

    def delete(self, device_id, owner=None):
        return self.transport.delete(
            self._url(device_id),
            params={'owner': owner}
        )
