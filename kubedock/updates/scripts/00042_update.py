from fabric.api import run

from kubedock.api.nodes import (
    get_kuberdock_logs_config,
    get_kuberdock_logs_pod_name,
)
from kubedock.kapi.podcollection import PodCollection
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.users.models import User
from kubedock.validation import check_internal_pod_data


CONF = '/etc/rsyslog.d/kuberdock.conf'
PARAM = '$LocalHostName'


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Add node hostname to rsyslog configuration...')

    run("sed -i '/^{0}/d; i{0} {1}' {2}".format(PARAM, env.host_string, CONF))
    run('systemctl restart rsyslog')

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

    run('rm -fr /var/lib/elasticsearch/kuberdock/nodes/*/indices/syslog-*')

    PodCollection(ki).update(logs_pod['id'], {'command': 'start'})


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
