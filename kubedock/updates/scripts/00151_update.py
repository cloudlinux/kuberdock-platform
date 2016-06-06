"""Add statically linked binaries to provide ssh access into containers."""
from kubedock.kapi.podcollection import PodCollection
from kubedock.kapi.pod import add_kdtools
from kubedock.pods.models import Pod
from kubedock.updates.helpers import remote_install, run
from kubedock.exceptions import APIError


def upgrade(upd, with_testing, *args, **kwargs):
    # Patch RC specs
    upd.print_log('Patch replication controllers to support ssh access...')
    pc = PodCollection()
    for dbpod in Pod.query.filter(Pod.status != 'deleted'):
        pod_id = dbpod.id
        pod = pc._get_by_id(pod_id)
        try:
            rc = pc._get_replicationcontroller(pod.namespace, pod.sid)
        except APIError:
            # there is no RC created for the pod yet, skip it.
            continue

        volumes = []
        containers = [
            {
                'name': container['name'],
                'volumeMounts': []
            }
            for container in pod.containers
        ]
        add_kdtools(containers, volumes)

        res = PodCollection().patch_running_pod(
            pod_id,
            {
                'spec': {
                    'volumes': volumes,
                    'containers': containers
                },
            },
            replace_lists=False,
            restart=False
        )
        res = res or {}
        upd.print_log('Updated pod: {}'.format(res.get('name', 'Unknown')))


def downgrade(upd, *args, **kwars):
    pass


def upgrade_node(upd, with_testing, *args, **kwargs):
    remote_install('kdtools', testing=with_testing)
    # Patch all containers to add kdtools directory
    run('for containerid in $(docker ps --format "{{.ID}}");'
        'do docker cp /usr/lib/kdtools/. $containerid:/.kdtools; done')


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    pass
