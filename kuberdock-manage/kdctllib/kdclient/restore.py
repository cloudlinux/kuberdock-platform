from .utils import ClientBase


class RestoreClient(ClientBase):
    endpoint = '/restore'

    def pod(self, pod_data, owner, volumes_dir_url):
        return self.transport.post(
            self._url('pod'),
            {
                'pod_data': pod_data,
                'owner': owner,
                'volumes_dir_url': volumes_dir_url,
            }
        )
