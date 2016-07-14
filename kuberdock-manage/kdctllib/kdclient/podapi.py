from .utils import ClientBase


class PodAPIClient(ClientBase):
    endpoint = '/podapi'

    def list(self, owner=None):
        return self.transport.get(
            self._url(),
            params={'owner': owner}
        )

    def get(self, pod_id, owner=None):
        return self.transport.get(
            self._url(pod_id),
            params={'owner': owner}
        )

    def create(self, pod_data, owner=None):
        return self.transport.post(
            self._url(),
            params={'owner': owner},
            json=pod_data
        )

    def update(self, pod_id, pod_data):
        # todo: add parameter "owner" in api/v2
        return self.transport.put(
            self._url(pod_id),
            json=pod_data
        )

    def delete(self, pod_id, owner=None):
        return self.transport.delete(
            self._url(pod_id),
            params={'owner': owner}
        )
