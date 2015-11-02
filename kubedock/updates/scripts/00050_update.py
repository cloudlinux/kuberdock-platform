import json
from kubedock.updates import helpers
from kubedock.pods.models import Pod, PersistentDisk
from kubedock.users.models import User, db
from kubedock.kapi.pstorage import CephStorage, AmazonStorage
from kubedock.kapi.helpers import KubeQuery
from kubedock.utils import POD_STATUSES
from kubedock.settings import CEPH, AWS


def get_pods_by_drives():
    pods = Pod.query.filter(Pod.status != 'deleted')
    pods_by_drives = {}
    for pod in pods:
        k8s_pods = KubeQuery()._get(['pods'], ns=pod.id).get('items', [])
        if not k8s_pods:
            continue
        status = k8s_pods[0].get('status', {}).get('phase', '').lower()
        if status not in (POD_STATUSES.running, POD_STATUSES.pending):
            continue
        try:
            config = json.loads(pod.config)
        except (TypeError, ValueError):
            continue
        volumes = config.get('volumes', None) or []
        for volume in volumes:
            if 'rbd' in volume:
                drive_name = volume['rbd']['image']
            elif 'awsElasticBlockStore' in volume:
                drive_name = volume['awsElasticBlockStore']['image']
            else:
                continue
            pods_by_drives[drive_name] = pod
    return pods_by_drives


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add PersistentDisk model.')
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='56f9182bf415')

    upd.print_log('Populate db...')
    drives = []
    if CEPH:
        drives.extend(CephStorage().get())
    if AWS:
        drives.extend(AmazonStorage().get())
    if not drives:
        return

    pods_by_drives = get_pods_by_drives()
    for drive in drives:
        owner = User.filter_by(username=drive['owner']).one()
        pod = pods_by_drives.get(drive['drive_name'])
        pd = PersistentDisk(id=drive['id'],
                            drive_name=drive['drive_name'],
                            name=drive['name'],
                            owner=owner,
                            size=drive['size'],
                            pod=pod)
        db.session.add(pd)
    db.session.commit()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Remove PersistentDisk model.')
    helpers.downgrade_db(revision='1ee2cbff529c')
