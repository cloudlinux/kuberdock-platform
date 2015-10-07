from fabric.api import run

from kubedock.utils import get_timezone


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    timezone = get_timezone()
    upd.print_log('Setting node timezone to {0}...'.format(timezone))
    run('timedatectl set-timezone {0}'.format(timezone))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
