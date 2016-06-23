from time import sleep

import requests
from contextlib2 import suppress

from kubedock import settings
from kubedock.settings import INFLUXDB_DATABASE, INFLUXDB_USER, \
    INFLUXDB_PASSWORD
from kubedock.updates import helpers


def _backup_file_remote(filename):
    backup_name = filename + '.bak'
    helpers.run('cp %s %s' % (filename, backup_name))


def _restore_backup_remote(filename):
    backup_name = filename + '.bak'
    helpers.run('cp %s %s' % (backup_name, filename))


def _replace_str_in_file_remote(filename, old_re, new):
    helpers.run("sed -i -r 's/%s/%s/g' %s" % (old_re, new, filename))

    
class InfluxUpdate(object):
    @staticmethod
    def upgrade(upd):
        upd.print_log('Update influxdb...')

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

    @staticmethod
    def downgrade(upd):
        upd.print_log('Downgrade influxdb...')
        helpers.install_package('influxdb', 'downgrade')


class HeapsterUpdate(object):
    @staticmethod
    def upgrade(upd):
        upd.print_log('Start heapster service...')
        helpers.local('systemctl reenable heapster')
        helpers.local('systemctl restart heapster')

    @staticmethod
    def downgrade(upd):
        upd.print_log('Stop and disable heapster service...')
        helpers.local('systemctl stop heapster')
        helpers.local('systemctl disable heapster')


class CadvisorUpdate(object):
    @staticmethod
    def upgrade(upd):
        upd.print_log('Remove kuberdock-cadvisor...')
        helpers.remote_install('kuberdock-cadvisor', action='remove')

    @staticmethod
    def downgrade(upd, with_testing):
        upd.print_log('Restore kuberdock-cadvisor...')
        helpers.remote_install('kuberdock-cadvisor-0.19.5', with_testing)
        helpers.run('systemctl reenable kuberdock-cadvisor')
        helpers.run('systemctl restart kuberdock-cadvisor')


class KubeletUpdate(object):
    KUBELET_CONFIG_FILE = '/etc/kubernetes/kubelet'

    @staticmethod
    def upgrade(upd):
        upd.print_log('Update kubelet config...')

        with suppress(Exception):
            _backup_file_remote(KubeletUpdate.KUBELET_CONFIG_FILE)

        _replace_str_in_file_remote(
            KubeletUpdate.KUBELET_CONFIG_FILE,
            '--cadvisor_port=\S+', '')
        _replace_str_in_file_remote(
            KubeletUpdate.KUBELET_CONFIG_FILE,
            'KUBELET_ADDRESS=".*"', 'KUBELET_ADDRESS="0.0.0.0"')
        helpers.run('systemctl restart kubelet')

    @staticmethod
    def downgrade(upd):
        upd.print_log('Restore kubelet config...')
        with suppress(Exception):
            _restore_backup_remote(KubeletUpdate.KUBELET_CONFIG_FILE)
        helpers.run('systemctl restart kubelet')


def upgrade(upd, with_testing, *args, **kwargs):
    InfluxUpdate.upgrade(upd)
    HeapsterUpdate.upgrade(upd)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    InfluxUpdate.downgrade(upd)
    HeapsterUpdate.downgrade(upd)


def upgrade_node(upd, with_testing, *args, **kwargs):
    CadvisorUpdate.upgrade(upd)
    KubeletUpdate.upgrade(upd)


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    CadvisorUpdate.downgrade(upd, with_testing)
    KubeletUpdate.downgrade(upd)
