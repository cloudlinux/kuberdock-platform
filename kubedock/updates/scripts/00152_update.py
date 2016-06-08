from time import sleep

import requests
from kubedock import settings
from kubedock.settings import INFLUXDB_DATABASE, INFLUXDB_USER, \
    INFLUXDB_PASSWORD
from kubedock.updates import helpers


def _update_influxdb(with_testing):
    # remove old version with all settings
    helpers.local('rm -rf /opt/influxdb')
    helpers.local('rm /etc/systemd/system/influxdb.service')
    helpers.local('systemctl daemon-reload')

    # install new version
    helpers.local('systemctl reenable influxdb')
    helpers.local('systemctl restart influxdb')

    # wait starting
    t = 1
    success = False
    ping_url = 'http://%s:%s/ping' % (
    settings.INFLUXDB_HOST, settings.INFLUXDB_PORT)
    for _ in xrange(5):
        try:
            requests.get(ping_url)
        except requests.ConnectionError:
            sleep(t)
            t *= 2
        else:
            success = True
            break
    if not success:
        raise helpers.UpgradeError('Influxdb does not answer to ping')

    # initialization
    helpers.local(
        'influx -execute "create user {user} with password \'{password}\' with all privileges"'
        .format(user=INFLUXDB_USER, password=INFLUXDB_PASSWORD))
    helpers.local('influx -execute "create database {db}"'
                  .format(db=INFLUXDB_DATABASE))


def _remove_cadvisor():
    helpers.remote_install('kuberdock-cadvisor', action='remove')


def _restore_cadvisor():
    helpers.remote_install('kuberdock-cadvisor-0.19.5')
    helpers.run('systemctl reenable kuberdock-cadvisor')
    helpers.run('systemctl restart kuberdock-cadvisor')


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update influxdb...')
    _update_influxdb(with_testing)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrade influxdb...')
    helpers.install_package('influxdb', 'downgrade')


def upgrade_node(upd, with_testing, *args, **kwargs):
    upd.print_log('Remove kuberdock-cadvisor...')
    _remove_cadvisor()


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Restore kuberdock-cadvisor...')
    _restore_cadvisor()
