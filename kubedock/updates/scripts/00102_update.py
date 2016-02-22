import os
import ConfigParser

from fabric.api import run, put

from kubedock.updates import helpers


PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='4ded025d2f29')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='2df8c40ab250')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    put('/var/opt/kuberdock/node_network_plugin.sh', PLUGIN_DIR + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py', PLUGIN_DIR + 'kuberdock.py')
    run('systemctl restart kuberdock-watcher')


def downgrade_node(upd, with_testing,  exception, *args, **kwargs):
    pass
