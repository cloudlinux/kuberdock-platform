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
    # restore
    pod_collection = PodCollection(owner=owner)
    restored_pod_dict = pod_collection.add(
        _extract_needed_information(pod_data)
    )
    pod_id = restored_pod_dict.get('id')
    assert pod_id

    if pod_data['status'] == 'running':
        pod_collection = PodCollection(owner=owner)
        restored_pod_dict = pod_collection.update(
            pod_id=pod_id,
            data={'command': 'start'}
        )
    # todo: add restore volumes

    return restored_pod_dict
