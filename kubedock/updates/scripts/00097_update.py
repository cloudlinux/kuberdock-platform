from fabric.api import run, put

from kubedock.users.models import User
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.kapi.nodes import (
    get_kuberdock_logs_config,
    get_kuberdock_logs_pod_name,
)
from kubedock.kapi.podcollection import PodCollection
from kubedock.validation import check_internal_pod_data

def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Update elasticsearch for logs...')
    upd.print_log(put('/var/opt/kuberdock/make_elastic_config.py',
                      '/var/lib/elasticsearch',
                      mode=0755))
    upd.print_log('Update logging pod...')
    ki = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    pod_name = get_kuberdock_logs_pod_name(env.host_string)

    for pod in PodCollection(ki).get(as_json=False):
        if pod['name'] == pod_name:
            break
    else:
        return

    PodCollection(ki).delete(pod['id'], force=True)
    logs_config = get_kuberdock_logs_config(
        env.host_string,
        pod_name,
        pod['kube_type'],
        pod['containers'][0]['kubes'],
        pod['containers'][1]['kubes'],
        MASTER_IP,
        ki.get_token(),
    )
    check_internal_pod_data(logs_config, user=ki)
    logs_pod = PodCollection(ki).add(logs_config, skip_check=True)

    run('docker pull kuberdock/elasticsearch:2.2')
    run('docker pull kuberdock/fluentd:1.5')

    PodCollection(ki).update(logs_pod['id'], {'command': 'start'})


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('No downgrades available')

