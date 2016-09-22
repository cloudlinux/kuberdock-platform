""" NOTE: on release merge it may be not needed at all because of 00187 -
which already copies node storage manage scripts to nodes.
"""
import os

from fabric.api import run, put, cd

PLUGIN_DIR = "/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/"
NODE_SCRIPT_DIR = '/var/lib/kuberdock/scripts'
NODE_STORAGE_MANAGE_DIR = 'node_storage_manage'
KD_INSTALL_DIR = '/var/opt/kuberdock'


# NOTE: don't include in merged upgrade script if there also will be merged
# 00187.
def upgrade_node_00188():
    target_script_dir = os.path.join(NODE_SCRIPT_DIR, NODE_STORAGE_MANAGE_DIR)
    run('mkdir -p ' + target_script_dir)
    scripts = [
        'aws.py', 'common.py', '__init__.py', 'manage.py',
        'node_lvm_manage.py', 'node_zfs_manage.py'
    ]
    for item in scripts:
        put(os.path.join(KD_INSTALL_DIR, NODE_STORAGE_MANAGE_DIR, item),
            target_script_dir)
    # Update symlink only if it not exists
    with cd(target_script_dir):
        run('ln -s node_lvm_manage.py storage.py 2> /dev/null || true')


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upgrade_node_00188()


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
