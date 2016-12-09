from kubedock.updates import helpers


K8S_VERSION = '1.2.4-7'
K8S = 'kubernetes-{name}-{version}.el7.cloudlinux'
K8S_NODE = K8S.format(name='node', version=K8S_VERSION)


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log("Upgrading kubernetes")
    helpers.remote_install(K8S_NODE, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError(
            'Failed to restart {0}. {1}'.format(service, res))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass

def upgrade(upd, with_testing, *args, **kwargs):
    helpers.restart_master_kubernetes()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass
