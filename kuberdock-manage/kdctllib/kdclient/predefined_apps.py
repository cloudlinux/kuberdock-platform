from .utils import ClientBase


class PredefinedAppsClient(ClientBase):
    endpoint = '/predefined-apps'

    def list(self, file_only=False):
        params = {'file-only': file_only}

        return self.transport.get(
            self._url(),
            params=params
        )

    def get(self, app_id, file_only=False):
        params = {'file-only': file_only}

        return self.transport.get(
            self._url(app_id),
            params=params
        )

    def create(self, app_data):
        return self.transport.post(
            self._url(),
            json=app_data
        )

    def update(self, app_id, app_data):
        return self.transport.put(
            self._url(app_id),
            json=app_data
        )

    def delete(self, app_id):
        return self.transport.delete(
            self._url(app_id)
        )

    def validate_template(self, template):
        return self.transport.post(
            self._url('validate-template'),
            json={'template': template}
        )
