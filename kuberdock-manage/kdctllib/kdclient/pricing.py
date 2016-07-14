from .utils import ClientBase


class PricingClient(ClientBase):
    endpoint = '/pricing'

    def __init__(self, client):
        super(PricingClient, self).__init__(client)
        self.license = LicenseClient(self)


class LicenseClient(ClientBase):
    endpoint = '/license'

    def show(self):
        return self.transport.get(
            self._url()
        )

    def set(self, installation_id):
        params = {"value": installation_id}
        return self.transport.post(
            self._url('installation_id'),
            params=params
        )
