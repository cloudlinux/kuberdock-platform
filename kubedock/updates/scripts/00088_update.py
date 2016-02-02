from fabric.api import run, put

PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('No upgrade provided for master')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('No downgrade provided for master')


def upgrade_node(upd, with_testing, *args, **kwargs):
    put('/var/opt/kuberdock/node_network_plugin.sh', PLUGIN_DIR + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py', PLUGIN_DIR + 'kuberdock.py')
    run('systemctl restart kuberdock-watcher')


def downgrade_node(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
