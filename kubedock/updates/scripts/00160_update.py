from abc import ABCMeta
from time import sleep

import requests
import ConfigParser
from contextlib2 import suppress
from fabric.operations import put, run, local

from kubedock import settings
from kubedock.exceptions import APIError
from kubedock.kapi.nodes import get_dns_pod_config, \
    get_dns_pod_config_pre_k8s_1_2
from kubedock.kapi.pod import add_kdtools
from kubedock.kapi.podcollection import PodCollection, \
    get_replicationcontroller
from kubedock.kapi.podcollection import wait_pod_status
from kubedock.nodes.models import Node
from kubedock.pods import Pod
from kubedock.rbac import fixtures as rbac_fixtures
from kubedock.updates import helpers
from kubedock.updates.helpers import restart_service, remote_install
from kubedock.users import User
from kubedock.utils import POD_STATUSES, randstr
from kubedock.validation import check_internal_pod_data
from node_network_plugin import PLUGIN_PATH
from node_network_plugin import PUBLIC_IP_POSTROUTING_RULE
from kubedock.settings import KUBERDOCK_SETTINGS_FILE


class _Update(object):
    __metaclass__ = ABCMeta

    @classmethod
    def upgrade(cls, upd, with_testing):
        pass

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        pass

    @classmethod
    def upgrade_node(cls, upd, with_testing, env):
        pass

    @classmethod
    def downgrade_node(cls, upd, with_testing, env, error):
        pass


class _UpgradeDB(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing):
        helpers.upgrade_db()

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        helpers.downgrade_db(revision='3dc83a81f385')
        helpers.downgrade_db(revision='3c832810a33c')


class _UpdatePermissions(_Update):
    new_resources = ['persistent_volumes']
    new_permissions = [
        ('persistent_volumes', 'Admin', 'create', False),
        ('persistent_volumes', 'Admin', 'create_non_owned', True),
        ('persistent_volumes', 'Admin', 'delete', False),
        ('persistent_volumes', 'Admin', 'delete_non_owned', True),
        ('persistent_volumes', 'Admin', 'edit', False),
        ('persistent_volumes', 'Admin', 'edit_non_owned', True),
        ('persistent_volumes', 'Admin', 'get', False),
        ('persistent_volumes', 'Admin', 'get_non_owned', True),
        ('persistent_volumes', 'Admin', 'own', False),
        ('persistent_volumes', 'LimitedUser', 'create', False),
        ('persistent_volumes', 'LimitedUser', 'create_non_owned', False),
        ('persistent_volumes', 'LimitedUser', 'delete', True),
        ('persistent_volumes', 'LimitedUser', 'delete_non_owned', False),
        ('persistent_volumes', 'LimitedUser', 'edit', True),
        ('persistent_volumes', 'LimitedUser', 'edit_non_owned', False),
        ('persistent_volumes', 'LimitedUser', 'get', True),
        ('persistent_volumes', 'LimitedUser', 'get_non_owned', False),
        ('persistent_volumes', 'LimitedUser', 'own', True),
        ('persistent_volumes', 'TrialUser', 'create', True),
        ('persistent_volumes', 'TrialUser', 'create_non_owned', False),
        ('persistent_volumes', 'TrialUser', 'delete', True),
        ('persistent_volumes', 'TrialUser', 'delete_non_owned', False),
        ('persistent_volumes', 'TrialUser', 'edit', True),
        ('persistent_volumes', 'TrialUser', 'edit_non_owned', False),
        ('persistent_volumes', 'TrialUser', 'get', True),
        ('persistent_volumes', 'TrialUser', 'get_non_owned', False),
        ('persistent_volumes', 'TrialUser', 'own', True),
        ('persistent_volumes', 'User', 'create', True),
        ('persistent_volumes', 'User', 'create_non_owned', False),
        ('persistent_volumes', 'User', 'delete', True),
        ('persistent_volumes', 'User', 'delete_non_owned', False),
        ('persistent_volumes', 'User', 'edit', True),
        ('persistent_volumes', 'User', 'edit_non_owned', False),
        ('persistent_volumes', 'User', 'get', True),
        ('persistent_volumes', 'User', 'get_non_owned', False),
        ('persistent_volumes', 'User', 'own', True),
        ('pods', 'Admin', 'create_non_owned', True),
        ('pods', 'Admin', 'delete_non_owned', True),
        ('pods', 'Admin', 'edit_non_owned', True),
        ('pods', 'Admin', 'get_non_owned', True),
        ('pods', 'Admin', 'own', False),
        ('pods', 'LimitedUser', 'create_non_owned', False),
        ('pods', 'LimitedUser', 'delete_non_owned', False),
        ('pods', 'LimitedUser', 'edit_non_owned', False),
        ('pods', 'LimitedUser', 'get_non_owned', False),
        ('pods', 'LimitedUser', 'own', True),
        ('pods', 'TrialUser', 'create_non_owned', False),
        ('pods', 'TrialUser', 'delete_non_owned', False),
        ('pods', 'TrialUser', 'edit_non_owned', False),
        ('pods', 'TrialUser', 'get_non_owned', False),
        ('pods', 'TrialUser', 'own', True),
        ('pods', 'User', 'create_non_owned', False),
        ('pods', 'User', 'delete_non_owned', False),
        ('pods', 'User', 'edit_non_owned', False),
        ('pods', 'User', 'get_non_owned', False),
        ('pods', 'User', 'own', True),
    ]

    @classmethod
    def upgrade(cls, upd, with_testing):
        upd.print_log('Upgrade permissions')
        rbac_fixtures.add_resources(cls.new_resources)
        rbac_fixtures._add_permissions(cls.new_permissions)

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        upd.print_log('Downgrade permissions')
        rbac_fixtures._delete_permissions(cls.new_permissions)
        rbac_fixtures.delete_resources(cls.new_resources)


class _U149(_Update):
    @classmethod
    def _recreate_dns_pod(cls, upd, dns_pod_config):
        upd.print_log("Deleting current DNS pod.")
        user = User.filter_by(username=settings.KUBERDOCK_INTERNAL_USER).one()
        dns_pod = Pod.filter_by(name='kuberdock-dns', owner=user).first()
        if dns_pod:
            PodCollection(user).delete(dns_pod.id, force=True)

        # Since usual upgrade is done with healthcheck
        #  we can assume all nodes are
        # in running state.
        nodes = Node.query.all()
        if not nodes:
            upd.print_log(
                "No nodes found on the cluster. The new DNS pod will be "
                "added once the 1st node is added to the cluster.")
            return

        check_internal_pod_data(dns_pod_config, user)
        dns_pod = PodCollection(user).add(dns_pod_config, skip_check=True)
        PodCollection(user).update(dns_pod['id'],
                                   {
                                       'command': 'start',
                                       'async-pod-create': False
                                   })
        # wait dns pod for 10 minutes
        upd.print_log(
            'Wait until DNS pod starts. It can take up to 10 minutes...')
        wait_pod_status(dns_pod['id'], POD_STATUSES.running, 30, 20)

    @classmethod
    def _upgrade_dns_pod(cls, upd):
        upd.print_log('Upgrading DNS pod...')
        dns_pod_config = get_dns_pod_config()
        cls._recreate_dns_pod(upd, dns_pod_config)

    @classmethod
    def _downgrade_dns_pod(cls, upd):
        upd.print_log('Downgrading DNS pod...')
        dns_pod_config = get_dns_pod_config_pre_k8s_1_2()
        cls._recreate_dns_pod(upd, dns_pod_config)

    @classmethod
    def upgrade(cls, upd, *args, **kwargs):
        cls._upgrade_dns_pod(upd)

    @classmethod
    def downgrade(cls, upd, *args, **kwargs):
        cls._downgrade_dns_pod(upd)


class _U150(_Update):
    NTP_CONF = '/etc/ntp.conf'
    ERASE_CHRONY_CMD = 'yum erase -y chrony'
    RESTART_NTPD = 'systemctl restart ntpd'
    # To prevent ntpd from exit on large time offsets
    SET_TINKER_PANIC = 'sed -i "/^tinker /d" {0};' \
                       'echo "tinker panic 0" >> {0}'.format(NTP_CONF)
    CHANGE_NODES_POLL_INTERVAL = \
        'sed -i "/^server /d" {0};' \
        'echo "server {1} iburst minpoll 3 maxpoll 4" >> {0}'.format(
            NTP_CONF, settings.MASTER_IP)

    @classmethod
    def upgrade(cls, *args, **kwargs):
        local(cls.ERASE_CHRONY_CMD)
        local(cls.SET_TINKER_PANIC)
        local(cls.RESTART_NTPD)

    @classmethod
    def upgrade_node(cls, *args, **kwargs):
        run(cls.ERASE_CHRONY_CMD)
        run(cls.SET_TINKER_PANIC)
        run(cls.CHANGE_NODES_POLL_INTERVAL)
        run(cls.RESTART_NTPD)


class _U151(_Update):
    KUBERNETES_PACKAGES = [
        'kubernetes-client-1.2.4-2.el7.cloudlinux',
        'kubernetes-node-1.2.4-2.el7.cloudlinux'
    ]

    OLD_KUBERNETES_PACKAGES = [
        'kubernetes-client-1.2.4-1.el7.cloudlinux',
        'kubernetes-node-1.2.4-1.el7.cloudlinux'
    ]

    KUBERDOCK_INI = '''NONFLOATING_PUBLIC_IPS={0}
    MASTER={1}
    NODE={2}
    TOKEN={3}'''

    @classmethod
    def add_kdtools_to_master(cls, upd):
        # Patch RC specs
        upd.print_log('Restart pods to support ssh access...')
        pc = PodCollection()
        query = Pod.query.filter(Pod.status != 'deleted')
        user = User.filter_by(username=settings.KUBERDOCK_INTERNAL_USER).one()
        dns_pod = Pod.filter_by(name='kuberdock-dns', owner=user).first()
        if dns_pod:
            query.filter(Pod.id != dns_pod.id)
        for dbpod in query:
            pod = pc._get_by_id(dbpod.id)
            if pod.status == POD_STATUSES.pending:
                # Workaround for AC-3386 issue: just don't restart
                # pending pods, because it may lead to error during pod start,
                # and upgrade script fail as a result.
                upd.print_log(
                    'Skip restart of pending pod "{}". '
                    'It may need manual restart to enable ssh access.'.format(
                        dbpod.name))
                continue
            pc._stop_pod(pod, block=True)
            pc._start_pod(pod, {'async_pod_create': False})
            upd.print_log('Restart pod: {}'.format(dbpod.name))

    @classmethod
    def add_kdtools_to_node(cls, with_testing):
        remote_install('kdtools', testing=with_testing)

    @classmethod
    def _upgrade_kubernetes(cls, with_testing):
        helpers.remote_install(' '.join(cls.KUBERNETES_PACKAGES), with_testing)
        service, res = helpers.restart_node_kubernetes()
        cls._raise_on_failure(service, res)

    @classmethod
    def _downgrade_kubernetes(cls, with_testing):
        helpers.remote_install(' '.join(cls.OLD_KUBERNETES_PACKAGES),
                               with_testing,
                               action='downgrade')
        service, res = helpers.restart_node_kubernetes()
        cls._raise_on_failure(service, res)

    @classmethod
    def _raise_on_failure(cls, service, res):
        if res != 0:
            raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                       .format(service, res))

    @classmethod
    def upgrade(cls, upd, *args, **kwargs):
        cls.add_kdtools_to_master(upd)

        # merged from 00155_update.py
        service, res = helpers.restart_master_kubernetes()
        cls._raise_on_failure(service, res)

    @classmethod
    def downgrade(cls, *args, **kwargs):
        # merged from 00155_update.py
        service, res = helpers.restart_master_kubernetes()
        cls._raise_on_failure(service, res)

    @classmethod
    def upgrade_node(cls, upd, with_testing, env, *args, **kwargs):
        cls.add_kdtools_to_node(with_testing)

        # merged from 00155_update.py
        upd.print_log('Upgrading kubernetes ...')
        cls._upgrade_kubernetes(with_testing)
        upd.print_log('Update network plugin...')
        put('/var/opt/kuberdock/node_network_plugin.sh',
            PLUGIN_PATH + 'kuberdock')
        put('/var/opt/kuberdock/node_network_plugin.py',
            PLUGIN_PATH + 'kuberdock.py')
        token = User.get_internal().get_token()
        ini = cls.KUBERDOCK_INI.format(
            'yes' if settings.NONFLOATING_PUBLIC_IPS else 'no',
            settings.MASTER_IP, env.host_string, token)
        run('echo "{0}" > "{1}"'.format(ini, PLUGIN_PATH + 'kuberdock.ini'))

    @classmethod
    def downgrade_node(cls, upd, with_testing, *args, **kwargs):
        # merged from 00155_update.py
        upd.print_log('Downgrading kubernetes ...')
        cls._downgrade_kubernetes(with_testing)


class _U152(_Update):
    class InfluxUpdate(object):
        @classmethod
        def upgrade(cls, upd):
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
                'influx -execute '
                '"create user {u} with password \'{p}\' with all privileges"'
                    .format(u=settings.INFLUXDB_USER,
                            p=settings.INFLUXDB_PASSWORD))
            helpers.local('influx -execute "create database {db}"'
                          .format(db=settings.INFLUXDB_DATABASE))

        @classmethod
        def downgrade(cls, upd):
            upd.print_log('Downgrade influxdb...')
            helpers.install_package('influxdb', 'downgrade')

    class HeapsterUpdate(object):
        @classmethod
        def upgrade(cls, upd):
            upd.print_log('Start heapster service...')
            helpers.local('systemctl reenable heapster')
            helpers.local('systemctl restart heapster')

        @classmethod
        def downgrade(cls, upd):
            upd.print_log('Stop and disable heapster service...')
            helpers.local('systemctl stop heapster')
            helpers.local('systemctl disable heapster')

    class CadvisorUpdate(object):
        @classmethod
        def upgrade(cls, upd):
            upd.print_log('Remove kuberdock-cadvisor...')
            helpers.remote_install('kuberdock-cadvisor', action='remove')

        @classmethod
        def downgrade(cls, upd, with_testing):
            upd.print_log('Restore kuberdock-cadvisor...')
            helpers.remote_install('kuberdock-cadvisor-0.19.5', with_testing)
            helpers.run('systemctl reenable kuberdock-cadvisor')
            helpers.run('systemctl restart kuberdock-cadvisor')

    class KubeletUpdate(object):
        KUBELET_CONFIG_FILE = '/etc/kubernetes/kubelet'

        @classmethod
        def _backup_file_remote(cls, filename):
            backup_name = filename + '.bak'
            helpers.run('cp %s %s' % (filename, backup_name))

        @classmethod
        def _restore_backup_remote(cls, filename):
            backup_name = filename + '.bak'
            helpers.run('cp %s %s' % (backup_name, filename))

        @classmethod
        def _replace_str_in_file_remote(cls, filename, old_re, new):
            helpers.run(
                "sed -i -r 's/%s/%s/g' %s" % (old_re, new, filename))

        @classmethod
        def upgrade(cls, upd):
            upd.print_log('Update kubelet config...')

            with suppress(Exception):
                cls._backup_file_remote(cls.KUBELET_CONFIG_FILE)

            cls._replace_str_in_file_remote(
                cls.KUBELET_CONFIG_FILE,
                '--cadvisor_port=\S+', '')
            cls._replace_str_in_file_remote(
                cls.KUBELET_CONFIG_FILE,
                'KUBELET_ADDRESS=".*"', 'KUBELET_ADDRESS="0.0.0.0"')
            helpers.run('systemctl restart kubelet')

        @classmethod
        def downgrade(cls, upd):
            upd.print_log('Restore kubelet config...')
            with suppress(Exception):
                cls._restore_backup_remote(cls.KUBELET_CONFIG_FILE)
            helpers.run('systemctl restart kubelet')

    @classmethod
    def upgrade(cls, upd, *args, **kwargs):
        cls.InfluxUpdate.upgrade(upd)
        cls.HeapsterUpdate.upgrade(upd)

    @classmethod
    def downgrade(cls, upd, *args, **kwargs):
        cls.InfluxUpdate.downgrade(upd)
        cls.HeapsterUpdate.downgrade(upd)

    @classmethod
    def upgrade_node(cls, upd, *args, **kwargs):
        cls.CadvisorUpdate.upgrade(upd)
        cls.KubeletUpdate.upgrade(upd)

    @classmethod
    def downgrade_node(cls, upd, with_testing, *args, **kwargs):
        cls.CadvisorUpdate.downgrade(upd, with_testing)
        cls.KubeletUpdate.downgrade(upd)


class _U156(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing):
        restart_service('nginx')


class _U157(_Update):
    KD_SCRIPTS_PATH_SRC = '/var/opt/kuberdock/node_scripts/'
    KD_SCRIPTS_PATH = '/var/lib/kuberdock/scripts/'

    SSHD_CONFIG_CMD = \
        """\
        ! grep -q 'kddockersshuser' /etc/ssh/sshd_config && \
        printf '\\nMatch group kddockersshuser
          PasswordAuthentication yes
          X11Forwarding no
          AllowTcpForwarding no
          ForceCommand /var/lib/kuberdock/scripts/kd-ssh-user.sh\\n' >> /etc/ssh/sshd_config
        """

    ADD_CRON_CMD = \
        """\
        KD_SSH_GC_PATH="/var/lib/kuberdock/scripts/kd-ssh-gc"
        KD_SSH_GC_LOCK="/var/run/kuberdock-ssh-gc.lock"
        KD_SSH_GC_CMD="flock -n $KD_SSH_GC_LOCK -c '$KD_SSH_GC_PATH;rm $KD_SSH_GC_LOCK'"
        KD_SSH_GC_CRON="@hourly  $KD_SSH_GC_CMD >/dev/null 2>&1"
        ! (crontab -l 2>/dev/null) | grep -q "$KD_SSH_GC_CRON" && \
        (crontab -l 2>/dev/null; echo "$KD_SSH_GC_CRON")| crontab -
        """

    @classmethod
    def upgrade(cls, upd, with_testing):
        # AC-3728
        upd.print_log('Disable unneeded dnsmasq...')
        local('systemctl stop dnsmasq')
        local('systemctl disable dnsmasq')

    @classmethod
    def upgrade_node(cls, upd, with_testing, env):
        upd.print_log('Copy KD ssh related scripts...')
        for scr in ('kd-docker-exec.sh', 'kd-ssh-gc', 'kd-ssh-user.sh',
                    'kd-ssh-user-update.sh'):
            put(cls.KD_SCRIPTS_PATH_SRC + scr, cls.KD_SCRIPTS_PATH + scr)
            run('chmod +x {}'.format(cls.KD_SCRIPTS_PATH + scr))

        upd.print_log('Configure sshd and cron...')
        run('groupadd kddockersshuser')
        run("! grep -q 'kddockersshuser' /etc/sudoers && "
            "echo -e '\\n%kddockersshuser ALL=(ALL) NOPASSWD: "
            "/var/lib/kuberdock/scripts/kd-docker-exec.sh' >> /etc/sudoers")
        run("! grep -q 'Defaults:%kddockersshuser' /etc/sudoers && "
            "echo -e '\\nDefaults:%kddockersshuser !requiretty' >> /etc/sudoers")
        run(cls.SSHD_CONFIG_CMD)
        run(cls.ADD_CRON_CMD)

        run('systemctl restart sshd.service')


class _U162(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing):
        # AC-3371
        if with_testing:
            cp = ConfigParser.ConfigParser()
            # Make option names case-sensitive
            cp.optionxform = str
            if cp.read(KUBERDOCK_SETTINGS_FILE) and cp.has_section('main'):
                upd.print_log('Enabling testing repo...')
                cp.set('main', 'WITH_TESTING', 'yes')
                with open(KUBERDOCK_SETTINGS_FILE, 'wb') as configfile:
                    cp.write(configfile)


class _U164(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing):
        fdata = open(KUBERDOCK_SETTINGS_FILE).read()
        if 'SECRET_KEY=' not in fdata:
            upd.print_log('Generating secret key...')
            with open(KUBERDOCK_SETTINGS_FILE, 'a') as c:
                c.write("SECRET_KEY={0}\n".format(randstr(32, secure=True)))


class _U165(_Update):
    @classmethod
    def upgrade_node(cls, upd, with_testing, env):
        upd.print_log('Update iptables rules ...')
        run('systemctl restart kuberdock-watcher')
        rv = run('iptables -L KUBERDOCK-PUBLIC-IP-SNAT -t nat')
        run('iptables -F KUBERDOCK-PUBLIC-IP-SNAT -t nat')
        ips = [(line.split()[3], line.split()[5].split(':')[1])
            for line in rv.splitlines()[2:]]
        for pod_ip, public_ip in ips:
            run(PUBLIC_IP_POSTROUTING_RULE.format('I', pod_ip, public_ip))


class _U168(_Update):

    @classmethod
    def upgrade_node(cls, upd, with_testing, env):
        upd.print_log('Update iptables rule...')

        # check if new rule already exists
        rv_n = run('iptables -w -C POSTROUTING -t nat ! -o flannel.1 '
                   '-j KUBERDOCK-PUBLIC-IP-SNAT')

        if rv_n.failed:
            # add new rule
            run('iptables -w -I POSTROUTING -t nat ! -o flannel.1 '
                '-j KUBERDOCK-PUBLIC-IP-SNAT')

        # check if old rule still exists
        rv_o = run('iptables -w -C POSTROUTING -t nat -j KUBERDOCK-PUBLIC-IP-SNAT')

        if rv_o.succeeded:
            # delete old rule
            run('iptables -w -D POSTROUTING -t nat -j KUBERDOCK-PUBLIC-IP-SNAT')


updates = [
    _UpgradeDB,
    _UpdatePermissions,
    _U149,
    _U150,
    _U151,
    _U152,
    _U156,
    _U157,
    _U162,
    _U164,
    _U165,
    _U168,
]


def _apply(method):
    def fn(*args):
        if method.startswith('down'):
            us = reversed(updates)
        else:
            us = updates

        for u in us:
            m = getattr(u, method)
            m(*args)

    return fn


upgrade = _apply('upgrade')
downgrade = _apply('downgrade')
upgrade_node = _apply('upgrade_node')
downgrade_node = _apply('downgrade_node')
