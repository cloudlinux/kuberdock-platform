from fabric.api import run, local
from kubedock.settings import MASTER_IP

NTP_CONF = '/etc/ntp.conf'
ERASE_CHRONY_CMD = 'yum erase -y chrony'
RESTART_NTPD = 'systemctl restart ntpd'
# To prevent ntpd from exit on large time offsets
SET_TINKER_PANIC = 'sed -i "/^tinker /d" {0};'\
                   'echo "tinker panic 0" >> {0}'.format(NTP_CONF)
CHANGE_NODES_POLL_INTERVAL = 'sed -i "/^server /d" {0};'\
    'echo "server {1} iburst minpoll 3 maxpoll 4" >> {0}'.format(
        NTP_CONF, MASTER_IP)


def upgrade(upd, with_testing, *args, **kwargs):
    local(ERASE_CHRONY_CMD)
    local(SET_TINKER_PANIC)
    local(RESTART_NTPD)


def downgrade(upd, *args, **kwars):
    pass


def upgrade_node(upd, with_testing, *args, **kwargs):
    run(ERASE_CHRONY_CMD)
    run(SET_TINKER_PANIC)
    run(CHANGE_NODES_POLL_INTERVAL)
    run(RESTART_NTPD)


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    pass
