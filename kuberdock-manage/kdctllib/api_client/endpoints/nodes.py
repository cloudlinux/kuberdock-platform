from ..base import ClientBase


class NodesClient(ClientBase):
    endpoint = '/nodes'

    def list(self):
        return self.transport.get(
            self._url()
        )

    def get(self, node_id):
        return self.transport.get(
            self._url(node_id)
        )

    def create(self, node_data):
        return self.transport.post(
            self._url(),
            json=node_data
        )

    def update(self, node_id, node_data):
        return self.transport.put(
            self._url(node_id),
            json=node_data
        )

    def delete(self, node_id):
        return self.transport.delete(
            self._url(node_id)
        )

    def check_host(self, hostname):
        return self.transport.get(
            self._url('checkhost', hostname)
        )
