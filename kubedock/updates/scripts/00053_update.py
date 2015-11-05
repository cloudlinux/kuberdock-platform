from fabric.api import run
from kubedock.settings import MASTER_IP, KUBERDOCK_SETTINGS_FILE


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    if not MASTER_IP:
        raise Exception('There is no MASTER_IP specified in {0}.'
                        'Check that file has not been renamed by package '
                        'manager to .rpmsave or similar'
                        .format(KUBERDOCK_SETTINGS_FILE))
    upd.print_log('Change ntp.conf to sync only with master...')
    upd.print_log(run('sed -i "/^server /d" /etc/ntp.conf'))
    upd.print_log(
        run('echo "server {0} iburst" >> /etc/ntp.conf'.format(MASTER_IP))
    )
    upd.print_log(run('systemctl restart ntpd'))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('No downgrade provided for this update. You may rerun '
                  'this upgrade script as many times as need or edit '
                  '/etc/ntp.conf manually.')
