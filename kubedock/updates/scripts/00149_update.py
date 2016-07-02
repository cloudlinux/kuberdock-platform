from kubedock.kapi.nodes import get_dns_pod_config, get_dns_pod_config_pre_k8s_1_2
from kubedock.kapi.podcollection import PodCollection, wait_pod_status
from kubedock.pods.models import Pod
from kubedock.settings import KUBERDOCK_INTERNAL_USER
from kubedock.users.models import User
from kubedock.utils import POD_STATUSES
from kubedock.validation import check_internal_pod_data
from kubedock.nodes.models import Node

# NOTE(lobur): this script cannot be merged into 148 (k8s & etcd upgrade)
# because it requires alive cluster to complete. If you put this to 148
# you'll get into situation when master is upgraded, nodes are not yet
# (old k8s ver), and you are trying to re-create pod on top - which is fails.


def _recreate_dns_pod(upd, dns_pod_config):
    upd.print_log("Deleting current DNS pod.")
    user = User.filter_by(username=KUBERDOCK_INTERNAL_USER).one()
    dns_pod = Pod.filter_by(name='kuberdock-dns', owner=user).first()
    if dns_pod:
        PodCollection(user).delete(dns_pod.id, force=True)

    # Since usual upgrade is done with healthcheck we can assume all nodes are
    # in running state.
    nodes = Node.query.all()
    if not nodes:
        upd.print_log("No nodes found on the cluster. The new DNS pod will be"
                      "added once the 1st node is added to the cluster.")
        return

    check_internal_pod_data(dns_pod_config, user)
    dns_pod = PodCollection(user).add(dns_pod_config, skip_check=True)
    PodCollection(user).update(dns_pod['id'],
                               {
                                   'command': 'start',
                                   'async-pod-create': False
                               })
    # wait dns pod for 10 minutes
    upd.print_log('Wait until DNS pod starts. It can take up to 10 minutes...')
    wait_pod_status(dns_pod['id'], POD_STATUSES.running, 30, 20)


def _upgrade_dns_pod(upd):
    upd.print_log('Upgrading DNS pod...')
    dns_pod_config = get_dns_pod_config()
    _recreate_dns_pod(upd, dns_pod_config)


def _downgrade_dns_pod(upd):
    upd.print_log('Downgrading DNS pod...')
    dns_pod_config = get_dns_pod_config_pre_k8s_1_2()
    _recreate_dns_pod(upd, dns_pod_config)


def upgrade(upd, with_testing, *args, **kwargs):
    _upgrade_dns_pod(upd)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    _downgrade_dns_pod(upd)
