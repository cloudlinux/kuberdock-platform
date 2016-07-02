
from .utils import ClientBase


class LicenseClient(ClientBase):
    endpoint = '/pricing'

    def show(self):
        return self.transport.get(
            self._url('license')
        )

    def set(self, license):
        params = {"value": license}
        return self.transport.post(
            self._url('license', 'installation_id'),
            params=params
        )
