from ..base import ClientBase


class StatsClient(ClientBase):
    endpoint = '/stats'

    def pod(self, pod_id):
        return self.transport.get(self._url('pods', pod_id))

    def container(self, pod_id, container_id):
        return self.transport.get(self._url(
            'pods', pod_id, 'containers', container_id))

    def node(self, node_id):
        return self.transport.get(self._url('nodes', node_id))
