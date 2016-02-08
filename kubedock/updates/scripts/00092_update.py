from fabric.api import put


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    put('/var/opt/kuberdock/node_network_plugin.sh',
        '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/kuberdock')


def downgrade_node(upd, with_testing,  exception, *args, **kwargs):
    pass
