from ..base import ClientBase


class SystemSettingsClient(ClientBase):
    endpoint = '/settings/sysapi'

    def list(self):
        return self.transport.get(
            self._url()
        )

    def get(self, id):
        return self.transport.get(
            self._url(id)
        )

    def update(self, id, value):
        return self.transport.put(
            self._url(id),
            json={'value': value}
        )
