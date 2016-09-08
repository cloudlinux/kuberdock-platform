import os

from fabric.api import run, put, cd

PLUGIN_DIR = "/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/"
NODE_SCRIPT_DIR = '/var/lib/kuberdock/scripts'
NODE_STORAGE_MANAGE_DIR = 'node_storage_manage'
KD_INSTALL_DIR = '/var/opt/kuberdock'


def upgrade_node_00183():
    put(os.path.join(KD_INSTALL_DIR, 'node_network_plugin.py'),
        os.path.join(PLUGIN_DIR, 'kuberdock.py'))
    target_script_dir = os.path.join(NODE_SCRIPT_DIR, NODE_STORAGE_MANAGE_DIR)
    run('mkdir -p ' + target_script_dir)
    put(os.path.join(KD_INSTALL_DIR, NODE_STORAGE_MANAGE_DIR) + '/*.py',
        target_script_dir)
    run('rm -f ' + os.path.join(target_script_dir, 'storage.py'))
    # Create symlink for current localstorage backend.
    # Previous versions had only one backend - LVM.
    # We don't switch already installed clusters to ZFS.
    with cd(target_script_dir):
        run('ln -s node_lvm_manage.py storage.py')


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upgrade_node_00183()


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
