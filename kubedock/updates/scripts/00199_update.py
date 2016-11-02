from kubedock.updates import helpers
from kubedock.users.models import User
from kubedock.pods.models import Pod
from kubedock.kapi.nodes import KUBERDOCK_DNS_POD_NAME, create_dns_pod
from kubedock.nodes.models import Node
from kubedock.kapi import node_utils
from kubedock.core import db
from kubedock.utils import NODE_STATUSES
from kubedock.kapi.podcollection import PodCollection


def upgrade(upd, with_testing, *args, **kwargs):
    ku = User.get_internal()
    pod = db.session.query(Pod).filter_by(
        name=KUBERDOCK_DNS_POD_NAME, owner=ku).first()
    nodes = Node.query.all()
    for node in nodes:
        k8s_node = node_utils._get_k8s_node_by_host(node.hostname)
        status, _ = node_utils.get_status(node, k8s_node)
        if status == NODE_STATUSES.running:
            if pod:
                pc = PodCollection()
                pc.delete(pod.id, force=True)
            create_dns_pod(node.hostname, ku)
            break
    else:
        raise helpers.UpgradeError("Can't find any running node to run dns pod")


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    pass
