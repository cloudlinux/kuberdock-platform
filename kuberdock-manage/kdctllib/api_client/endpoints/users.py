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

    def get(self, uid, short=False, with_deleted=False):
        return self.transport.get(
            self._url(uid),
            params={
                'short': short,
                'with-deleted': with_deleted
            }
        )

    def create(self, user_data):
        return self.transport.post(
            self._url(),
            json=user_data
        )

    def update(self, uid, user_data):
        return self.transport.put(
            self._url(uid),
            json=user_data
        )

    def delete(self, uid, force=False):
        return self.transport.delete(
            self._url(uid),
            params={'force': force}
        )
