from ..base import ClientBase


class UsersClient(ClientBase):
    endpoint = '/users/all'

    def list(self, short=False, with_deleted=False):
        return self.transport.get(
            self._url(),
            params={
                'short': short,
                'with-deleted': with_deleted
            }
        )

    def get(self, id, short=False, with_deleted=False):
        return self.transport.get(
            self._url(id),
            params={
                'short': short,
                'with-deleted': with_deleted
            }
        )

    def create(self, data):
        return self.transport.post(
            self._url(),
            json=data
        )

    def update(self, id, data):
        return self.transport.put(
            self._url(id),
            json=data
        )

    def delete(self, id, force=False):
        return self.transport.delete(
            self._url(id),
            params={'force': force}
        )
