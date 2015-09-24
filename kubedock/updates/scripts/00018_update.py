from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    helpers.install_package('kubernetes-master-1.0.3', with_testing)
    helpers.restart_master_kubernetes()

def downgrade(upd, with_testing,  exception, *args, **kwargs):
    helpers.local('yum downgrade kubernetes-master --enablerepo=kube')
    helpers.restart_master_kubernetes()

def upgrade_node(upd, with_testing, env, *args, **kwargs):
    helpers.remote_install('kubernetes-node-1.0.3', with_testing)
    helpers.restart_node_kubernetes()

def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
   helpers.remote_install('kubernetes-node', action='downgrade', testing=with_testing)
   helpers.restart_node_kubernetes()