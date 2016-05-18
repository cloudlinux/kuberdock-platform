from .utils import ClientBase


class SystemSettingsClient(ClientBase):
    endpoint = '/settings/sysapi'

    def list(self):
        return self.transport.get(
            self._url()
        )

    def get(self, sid):
        return self.transport.get(
            self._url(sid)
        )

    def update(self, sid, value):
        return self.transport.put(
            self._url(sid),
            data={'value': value}
        )
