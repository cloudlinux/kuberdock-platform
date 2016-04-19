import ConfigParser

from kubedock.updates import helpers

ETCD_VERSION = '2.2.5'
ETCD = 'etcd-{version}'.format(version=ETCD_VERSION)
ETCD_SERVICE_FILE = '/etc/systemd/system/etcd.service'


def _upgrade_etcd():
    # update config
    cp = ConfigParser.ConfigParser()
    with open(ETCD_SERVICE_FILE) as f:
        cp.readfp(f)

    cp.set('Service', 'Type', 'notify')
    with open(ETCD_SERVICE_FILE, "w") as f:
        cp.write(f)


def _downgrade_etcd():
    # downgrade config
    cp = ConfigParser.ConfigParser()
    with open(ETCD_SERVICE_FILE) as f:
        cp.readfp(f)

    cp.set('Service', 'Type', 'simple')
    with open(ETCD_SERVICE_FILE, "w") as f:
        cp.write(f)


def upgrade(upd, with_testing, *args, **kwargs):
    _upgrade_etcd()
    helpers.restart_master_kubernetes()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    _downgrade_etcd()
    helpers.restart_master_kubernetes()
