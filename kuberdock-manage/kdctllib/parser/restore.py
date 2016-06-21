import click

from main import main
from utils import data_argument
from ..kdclient.exceptions import APIError


@main.group(help='Restore objects from backups.')
def restore():
    pass


class _RestorePod(object):
    def __init__(self, kdclient, pod_data, owner, volumes_dir_url, force):
        self.kdclient = kdclient
        self.pod_data = pod_data
        self.owner = owner
        self.volumes_dir_url = volumes_dir_url
        self.force = force

    def __call__(self):
        try:
            self.kdclient.restore.pod(
                self.pod_data, self.owner, self.volumes_dir_url)
        except APIError as e:
            self._dispatch_errors(e)
            self.__call__()

    def _dispatch_errors(self, error):
        e_type = error.type
        if e_type == 'MultipleErrors':
            errors = [APIError(e['data'], e['type'], e['details'])
                      for e in error.details['errors']]
            for e in errors:
                self._dispatch_errors(e)
        elif e_type == 'PodNameConflict':
            self._try_delete_pod(error.details)
        elif e_type == 'VolumeExists':
            self._try_delete_pv(error.details)
        else:
            raise error

    def _try_delete_pod(self, pod_data):
        click.echo('Pod with name "{name}" already exists.'.format(**pod_data))
        if not self.force:
            if not click.confirm('Do you want to delete this pod?'):
                click.get_current_context().abort()
        click.echo('Deleting...')
        pod_id = pod_data.get('id')
        self.kdclient.pods.delete(pod_id=pod_id, owner=self.owner)
        click.echo('Deleted')

    def _try_delete_pv(self, pv_data):
        click.echo('Persistent volume with name "{name}" already exists.'
                   .format(**pv_data))
        if not self.force:
            if not click.confirm('Do you want to delete '
                                 'this persistent volume?'):
                click.get_current_context().abort()
        click.echo('Deleting...')
        pv_id = pv_data.get('id')
        self.kdclient.pstorage.delete(device_id=pv_id, owner=self.owner)
        click.echo('Deleted')


@restore.command(help='Restore pod.')
@data_argument('pod-data')
@click.option('--owner')
@click.option('--volumes-dir-url')
@click.option('--force', is_flag=True,
              help='Force deletion of pods and persistent volumes.')
@click.pass_obj
def pod(obj, pod_data, owner, volumes_dir_url, force):
    _RestorePod(obj.client, pod_data, owner, volumes_dir_url, force)()
    return 'OK'
