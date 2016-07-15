import click

from main import main
from utils import data_argument
from ..kdclient.exceptions import APIError


@main.group(help='Commands for restore objects from backups.')
def restore():
    pass


# bit flags
_NOT_FORCE = 0
_FORCE_DELETE = 1
_FORCE_NOT_DELETE = 2


class _RestorePodCommand(object):
    def __init__(self, kdctl, io, pod_data, owner, volumes_dir_url, force,
                 max_tries):
        assert force in [_NOT_FORCE, _FORCE_DELETE, _FORCE_NOT_DELETE]
        self.kdctl = kdctl
        self.io = io
        self.pod_data = pod_data
        self.owner = owner
        self.volumes_dir_url = volumes_dir_url
        self.force = force
        self.max_tries = max_tries

    def __call__(self):
        return self._apply(try_number=0)

    def _apply(self, try_number):
        try:
            return self.kdctl.restore.pod(
                self.pod_data, self.owner, self.volumes_dir_url)
        except APIError as e:
            if self.force == _FORCE_NOT_DELETE or try_number >= self.max_tries:
                raise
            self._dispatch_errors(e)
            return self._apply(try_number + 1)

    def _dispatch_errors(self, error):
        e_type = error.json['type']
        if e_type == 'MultipleErrors':
            errors = [APIError(e)
                      for e in error.json['details']['errors']]
            for e in errors:
                self._dispatch_errors(e)
        elif e_type == 'PodNameConflict':
            self._try_delete_pod(error.json['details'])
        elif e_type == 'VolumeExists':
            self._try_delete_pv(error.json['details'])
        else:
            raise error

    def _try_delete_pod(self, pod_data):
        assert self.force in [_NOT_FORCE, _FORCE_DELETE]
        kdctl = self.kdctl
        io = self.io
        io.out_text('Pod with name "%s" already exists.' % pod_data['name'])
        if self.force == _NOT_FORCE:
            if not io.confirm('Do you want to delete this pod?'):
                click.get_current_context().abort()
        io.out_text('Deleting...')
        pod_id = pod_data.get('id')
        kdctl.pods.delete(pod_id=pod_id, owner=self.owner)
        io.out_text('Deleted')

    def _try_delete_pv(self, pv_data):
        assert self.force in [_NOT_FORCE, _FORCE_DELETE]
        kdctl = self.kdctl
        io = self.io
        io.out_text('Persistent volume with name "%s" already exists.'
                    % pv_data['name'])
        if self.force == _NOT_FORCE:
            if not io.confirm('Do you want to delete this persistent volume?'):
                click.get_current_context().abort()
        io.out_text('Deleting...')
        pv_id = pv_data.get('id')
        kdctl.pstorage.delete(device_id=pv_id, owner=self.owner)
        io.out_text('Deleted')


def _check_params(io, force):
    if io.json_only and force == _NOT_FORCE:
        raise click.UsageError(
            'In json-only mode one of --force-delete/--force-not-delete '
            'options must be specified')


def _max_tries_validation(ctx, param, value):
    conditions = [
        value is None or value >= 0
    ]
    if not all(conditions):
        raise click.BadParameter('Value must be >= 0')
    if value == 0:
        return float('inf')
    return value


def _collect_force(force_delete, force_not_delete):
    # collect bit flags
    force = (force_delete and _FORCE_DELETE) + \
            (force_not_delete and _FORCE_NOT_DELETE)

    # check if only one flag or no flags specified
    if force & (force - 1) != 0:
        raise click.UsageError('"force-delete" and "force-not-delete" '
                               'are mutually exclusive options')

    # return result
    return force


@restore.command(help='Restore pod.')
@data_argument('pod-data')
@click.option('--owner')
@click.option('--volumes-dir-url')
@click.option('--force-delete', is_flag=True,
              help='Force delete pods and persistent volumes.')
@click.option('--force-not-delete', is_flag=True,
              help='Force NOT delete pods and persistent volumes.')
@click.option('--max-tries', type=int, callback=_max_tries_validation,
              default=2, show_default=True,
              help='Maximal number of tries, 0 for infinity.')
@click.pass_obj
def pod(obj, pod_data, owner, volumes_dir_url, force_delete, force_not_delete,
        max_tries):
    kdctl = obj.kdctl
    io = obj.io
    force = _collect_force(force_delete, force_not_delete)
    _check_params(io, force)
    command = _RestorePodCommand(
        kdctl, io, pod_data, owner, volumes_dir_url, force, max_tries)
    return command()
