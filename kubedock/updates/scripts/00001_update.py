from kubedock.updates import helpers
from fabric.api import run


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Test_master_upgrade 1', helpers.local('uname -a'))
    helpers.upgradedb()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Test_master_downgrade 1')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Upgrade node test')
    print run('uname -a')


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('In downgrade node')
