from kubedock.users.models import User
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.kapi.nodes import (
    get_kuberdock_logs_config,
    get_kuberdock_logs_pod_name,
)
from kubedock.validation import check_internal_pod_data
from kubedock.kapi.podcollection import PodCollection


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update logging pods...')

    ki = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    for pod in PodCollection(ki).get(as_json=False):
        if pod['name'] == get_kuberdock_logs_pod_name(pod['node']):
            PodCollection(ki).delete(pod['id'], force=True)
            logs_config = get_kuberdock_logs_config(
                pod['node'],
                pod['name'],
                pod['kube_type'],
                pod['containers'][0]['kubes'],
                pod['containers'][1]['kubes'],
                MASTER_IP,
                ki.get_token(),
            )
            check_internal_pod_data(logs_config, user=ki)
            logs_pod = PodCollection(ki).add(logs_config, skip_check=True)

            PodCollection(ki).update(logs_pod['id'], {'command': 'start'})


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade available.')
