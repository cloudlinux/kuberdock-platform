from ..base import ClientBase


class DomainsClient(ClientBase):
    endpoint = '/domains'

    def list(self):
        return self.transport.get(
            self._url(),
        )

    def get(self, id):
        return self.transport.get(
            self._url(id),
        )

    def create(self, name):
        data = {'name': name}
        return self.transport.post(
            self._url(),
            json=data
        )

    def update(self, id, new_name):
        data = {'name': new_name}
        return self.transport.put(
            self._url(id),
            json=data
        )

    def delete(self, id):
        return self.transport.delete(
            self._url(id)
        )
