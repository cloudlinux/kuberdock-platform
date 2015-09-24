import re

from kubedock.api.nodes import (
    get_kuberdock_logs_config,
    get_kuberdock_logs_pod_name,
)
from kubedock.kapi.podcollection import PodCollection
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.users.models import User
from kubedock.validation import check_new_pod_data
from kubedock.updates import helpers

pod_name_pattern = re.compile(get_kuberdock_logs_pod_name('.+?'))


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='38bc6f56f2aa')
    ki = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    for pod in PodCollection(ki).get(as_json=False):
        if pod_name_pattern.match(pod['name']):
            PodCollection(ki).delete(pod['id'], force=True)
            logs_config = get_kuberdock_logs_config(
                pod['node'],
                pod['name'],
                pod['kube_type'],
                pod['containers'][0]['kubes'],
                pod['containers'][1]['kubes'],
                MASTER_IP,
                ki.token,
            )
            check_new_pod_data(logs_config, user=ki)
            logs_pod = PodCollection(ki).add(logs_config)
            PodCollection(ki).update(logs_pod['id'], {'command': 'start'})


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
