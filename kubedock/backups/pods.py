from kubedock.exceptions import APIError
from kubedock.kapi.podcollection import PodCollection
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
    pod_collection = PodCollection(owner=owner)
    pod_spec = _extract_needed_information(pod_data)

    if len(_filter_persistent_volumes(pod_spec)) > 0:
        if not volumes_dir_url:
            raise APIError(
                'POD spec contains persistent volumes but volumes dir URL was '
                'not specified')
        pod_spec['volumes_dir_url'] = volumes_dir_url

    restored_pod_dict = pod_collection.add(pod_spec)

    if pod_data['status'] == 'running':
        pod_collection = PodCollection(owner=owner)
        restored_pod_dict = pod_collection.update(
            pod_id=restored_pod_dict['id'], data={'command': 'start'}
        )
    return restored_pod_dict
