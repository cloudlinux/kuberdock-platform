from .utils import ClientBase


class RestoreClient(ClientBase):
    endpoint = '/restore'

    def pod(self, pod_data, owner, pv_backups_location=None,
            pv_backups_path_template=None):
        return self.transport.post(
            self._url('pod'),
            json={
                'pod_data': pod_data,
                'owner': owner,
                'pv_backups_location': pv_backups_location,
                'pv_backups_path_template': pv_backups_path_template
            }
        )
