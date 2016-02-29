import os
from fabric.api import get, put

from kubedock.updates import helpers

KUBELET_PATH = '/etc/kubernetes/kubelet'
KUBELET_ARG = 'KUBELET_ARGS'
KUBELET_MULTIPLIERS = ' --cpu-multiplier=8 --memory-multiplier=4'
KUBELET_TEMP_PATH = '/tmp/kubelet'


def upgrade(upd, with_testing, *args, **kwargs):
    res = helpers.install_package('kubernetes-master-1.1.3', with_testing)
    if res:
        raise helpers.UpgradeError('Failed to update kubernetes on master')
    helpers.restart_master_kubernetes()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    res = helpers.remote_install('kubernetes-node-1.1.3', with_testing)
    upd.print_log(res)
    if res.failed:
        raise helpers.UpgradeError('Failed to update kubernetes on node')
    get(KUBELET_PATH, KUBELET_TEMP_PATH)
    lines = []
    with open(KUBELET_TEMP_PATH) as f:
        lines = f.readlines()
    with open(KUBELET_TEMP_PATH, 'w+') as f:
        for line in lines:
            if KUBELET_ARG in line and KUBELET_MULTIPLIERS not in line:
                s = line.split('"')
                s[1] += KUBELET_MULTIPLIERS
                line = '"'.join(s)
            f.write(line)
    put(KUBELET_TEMP_PATH, KUBELET_PATH)
    os.remove(KUBELET_TEMP_PATH)
    helpers.restart_node_kubernetes(with_enable=True)


def downgrade_node(upd, with_testing,  exception, *args, **kwargs):
    pass
