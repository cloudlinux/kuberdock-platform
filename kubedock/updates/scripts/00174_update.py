from fabric.operations import run

from kubedock.updates import helpers

K8S_VERSION = '1.2.4-3'
K8S = 'kubernetes-{name}-{version}.el7.cloudlinux'
K8S_NODE = K8S.format(name='node', version=K8S_VERSION)


# NOTE(lobur): this script should came one of the first in the 1.5.0 upgrade
# When upgrade is started it installs the new k8s on master (via rpm
# dependency) This script then updates node k8s version to match
# the new master. Until that cluster is not alive, that's why it should be
# at the beginning.


def _upgrade_k8s_node(upd, with_testing):
    upd.print_log("Upgrading kubernetes")
    helpers.remote_install(K8S_NODE, with_testing)


def _downgrade_k8s_node(upd, with_testing):
    pass


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _upgrade_k8s_node(upd, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
