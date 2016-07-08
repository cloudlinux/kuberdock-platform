from fabric.operations import put
from node_network_plugin import PLUGIN_PATH


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, *args, **kwars):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Update network plugin...')
    put('/var/opt/kuberdock/node_network_plugin.py',
        PLUGIN_PATH + 'kuberdock.py')


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    pass
