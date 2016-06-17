from .utils import ClientBase


class AuthClient(ClientBase):
    endpoint = '/auth'

    def token(self):
        return self.transport.get(
            self._url('token')
        )

    def token2(self, username, password):
        return self.transport.post(
            self._url('token2'),
            json={
                'username': username,
                'password': password
            }
        )
