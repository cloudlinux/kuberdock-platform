from ..base import ClientBase


class PredefinedAppsClient(ClientBase):
    endpoint = '/predefined-apps'

    def list(self, file_only=False):
        params = {'file-only': file_only}

        return self.transport.get(
            self._url(),
            params=params
        )

    def get(self, id, file_only=False):
        params = {'file-only': file_only}

        return self.transport.get(
            self._url(id),
            params=params
        )

    def create(self, name, origin, template, validate=None):
        json = {
            'name': name,
            'origin': origin,
            'template': template,
            'validate': validate,
        }
        return self.transport.post(
            self._url(),
            json=json
        )

    def update(self, id, template=None, validate=None):
        json = {
            'template': template,
            'validate': validate,
        }
        return self.transport.put(
            self._url(id),
            json=json
        )

    def delete(self, id):
        return self.transport.delete(
            self._url(id)
        )

    def validate_template(self, template):
        endpoint = 'validate-template'

        json = {'template': template}
        return self.transport.post(
            self._url(endpoint),
            json=json
        )

    def create_pod(self, template_id, plan_id, data):
        # redirect to yaml_api
        return self._YamlClient(self.client) \
            .create_pod(template_id, plan_id, data)

    class _YamlClient(ClientBase):
        endpoint = '/yamlapi'

        def create_pod(self, template_id, plan_id, data):
            return self.transport.post(
                self._url('create', template_id, plan_id),
                json=data
            )
