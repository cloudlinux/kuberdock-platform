from .utils import ClientBase


class BackupClient(ClientBase):
    endpoint = '/backup'

    def pod(self, *args, **kwargs):
        raise NotImplementedError
