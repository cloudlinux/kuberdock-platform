"""AC-5288 Update some node storage scripts"""
import os

from fabric.operations import put

NODE_SCRIPT_DIR = '/var/lib/kuberdock/scripts'
NODE_STORAGE_MANAGE_DIR = 'node_storage_manage'
KD_INSTALL_DIR = '/var/opt/kuberdock'


def _update_00220_upgrade_node():
    target_script_dir = os.path.join(NODE_SCRIPT_DIR, NODE_STORAGE_MANAGE_DIR)
    scripts = ['aws.py', 'manage.py']
    for item in scripts:
        put(os.path.join(KD_INSTALL_DIR, NODE_STORAGE_MANAGE_DIR, item),
            os.path.join(target_script_dir, item))


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _update_00220_upgrade_node()


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass
