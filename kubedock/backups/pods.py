from kubedock.exceptions import APIError
from kubedock.kapi.pod import VolumeExists
from kubedock.kapi.podcollection import PodCollection
from kubedock.pods.models import Pod as DBPod, PersistentDisk, \
    PersistentDiskStatuses
from kubedock.users import User


def _extract_needed_information(full_pod_config):
    fields = [
        'containers',
        'kube_type',
        'name',
        'replicas',
        'restartPolicy',
        'template_id',
        'volumes',
    ]
    return {
        k: full_pod_config.get(k, None)
        for k in fields
        }


def _filter_persistent_volumes(pod_spec):
    def is_local_storage(x):
        return bool(x.get('persistentDisk', {}).get('pdName'))

    return [v for v in pod_spec['volumes'] if is_local_storage(v)]


class MultipleErrors(APIError):
    message = 'Multiple errors'

    def __init__(self, errors):
        details = {
            'errors': [
                {
                    'data': e.message,
                    'type': getattr(e, 'type', e.__class__.__name__),
                    'details': e.details
                }
                for e in errors
                ]
        }
        super(MultipleErrors, self).__init__(details=details)


class _PodRestore(object):
    def __init__(self, pod_data, owner, volumes_dir_url):
        self.pod_data = pod_data
        self.owner = owner
        self.volumes_dir_url = volumes_dir_url

    def __call__(self):
        pod_spec = _extract_needed_information(self.pod_data)

        if _filter_persistent_volumes(pod_spec):
            if not self.volumes_dir_url:
                raise APIError(
                    'POD spec contains persistent volumes '
                    'but volumes dir URL was not specified')
            pod_spec['volumes_dir_url'] = self.volumes_dir_url

        self._check_for_conflicts(pod_spec)

        pod_collection = PodCollection(owner=self.owner)
        restored_pod_dict = pod_collection.add(pod_spec, reuse_pv=False)

        if self.pod_data['status'] == 'running':
            pod_collection = PodCollection(owner=self.owner)
            restored_pod_dict = pod_collection.update(
                pod_id=restored_pod_dict['id'], data={'command': 'start'}
            )
        return restored_pod_dict

    def _check_for_conflicts(self, pod_spec):
        errors = []
        e = self._check_pod_name(pod_spec['name'])
        if e:
            errors.append(e)

        vols = _filter_persistent_volumes(pod_spec)
        for vol in vols:
            e = self._check_volume_name(vol['persistentDisk']['pdName'])
            if e:
                errors.append(e)
        if errors:
            raise MultipleErrors(errors)

    def _check_pod_name(self, pod_name):
        pod = DBPod.query.filter(
            DBPod.name == pod_name, DBPod.owner_id == self.owner.id
        ).first()
        if pod:
            return APIError(
                'Pod with name "{0}" already exists.'.format(pod_name),
                status_code=409, type='PodNameConflict',
                details={'id': pod.id, 'name': pod.name}
            )

    def _check_volume_name(self, volume_name):
        persistent_disk = PersistentDisk.filter(
            PersistentDisk.owner_id == self.owner.id,
            PersistentDisk.name == volume_name,
            PersistentDisk.state.in_([
                PersistentDiskStatuses.PENDING,
                PersistentDiskStatuses.CREATED
            ])
        ).first()
        if persistent_disk:
            return VolumeExists(persistent_disk.name, persistent_disk.id)


def restore(pod_data, owner, volumes_dir_url=None):
    """
    Restore pod from backup.

    Args:
        pod_data (dict): Dictionary with full pod description.
        owner (User): Pod's owner.
        volumes_dir_url (str): Ftp url where dirs have following structures:
            backups/<node_id>/<user_id>/<vol1_name>

    Returns:
        dict: Dictionary with restored pod's data.

    Notes:
        Expected that pod_config contains full information
        got from postgres.
    """
    return _PodRestore(pod_data, owner, volumes_dir_url)()
