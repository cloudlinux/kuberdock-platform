from kubedock.pods.models import Pod
from kubedock.kapi.podcollection import PodCollection


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Restart pods with persistent storage')
    pc = PodCollection()
    pods = Pod.query.with_entities(Pod.id).filter(Pod.persistent_disks).all()
    for pod_id in pods:
        p = pc._get_by_id(pod_id[0])
        pc._stop_pod(p)
        pc._collection.pop((pod_id[0], pod_id[0]))
        pc._merge()
        p = pc._get_by_id(pod_id[0])
        pc._start_pod(p)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade available.')
