from kubedock.settings import CEPH
from kubedock.updates import helpers
from fabric.api import run


def upgrade(upd, with_testing, *args, **kwargs):
    if CEPH:
        helpers.local("""sed -i '/^KUBE_ALLOW_PRIV/ {s/--allow_privileged=false/--allow_privileged=true/}' /etc/kubernetes/config""")
        helpers.local('systemctl restart kube-apiserver')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    if CEPH:
        run("""sed -i '/^KUBE_ALLOW_PRIV/ {s/--allow_privileged=false/--allow_privileged=true/}' /etc/kubernetes/config""")
        run('systemctl restart kubelet')


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade_node provided')