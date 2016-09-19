import os
import subprocess
from abc import ABCMeta

from fabric.api import run, put, lcd, local
from fabric.context_managers import quiet
from sqlalchemy import Table

from kubedock.rbac import fixtures as rbac_fixtures
from kubedock.settings import AWS
from kubedock.settings import MASTER_IP
from kubedock.static_pages.fixtures import Menu, MenuItem, MenuItemRole, Role
from kubedock.static_pages.models import db
from kubedock.system_settings import keys
from kubedock.system_settings.models import SystemSettings
from kubedock.updates import helpers
from node_network_plugin import PLUGIN_PATH


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


class _U163(_Update):
    HOSTNAME = os.environ.get("HOSTNAME")
    KUBERNETES_CERTS_DIR = '/etc/kubernetes/certs'

    K8S_TLS_CERT = "{0}/{1}.crt".format(KUBERNETES_CERTS_DIR, HOSTNAME)
    K8S_TLS_PRIVATE_KEY = "{0}/{1}.key".format(KUBERNETES_CERTS_DIR, HOSTNAME)
    K8S_CA_CERT = KUBERNETES_CERTS_DIR + '/ca.crt'

    @classmethod
    def upgrade(cls, upd, with_testing, *args, **kwargs):
        # upd.print_log("Generating key for service account")
        sans = "IP:{0},IP:10.254.0.1,DNS:kubernetes,DNS:kubernetes.default,DNS:kubernetes.default.svc,DNS:$(hostname)".format(
            MASTER_IP)
        tempdir = local('mktemp -d', capture=True)
        with lcd(tempdir):
            local(
                'curl -k -L -O --connect-timeout 20 --retry 6 --retry-delay 2 '
                'https://storage.googleapis.com/kubernetes-release/easy-rsa/'
                'easy-rsa.tar.gz')
            local('tar xzf easy-rsa.tar.gz')
        with lcd(os.path.join(tempdir, 'easy-rsa-master/easyrsa3')):
            local('./easyrsa init-pki')
            local('./easyrsa --batch "--req-cn={primary_cn}@$(date +%s)" '
                  'build-ca nopass'.format(primary_cn=MASTER_IP))
            local('./easyrsa --subject-alt-name="{sans}" build-server-full '
                  '"$(hostname)" nopass'.format(sans=sans))

            local(
                'mkdir -p {certs_dir}'.format(
                    certs_dir=cls.KUBERNETES_CERTS_DIR))
            local('mv ./pki/ca.crt {certs_dir}/'
                  .format(certs_dir=cls.KUBERNETES_CERTS_DIR))
            local('mv ./pki/issued/* {certs_dir}/'
                  .format(certs_dir=cls.KUBERNETES_CERTS_DIR))
            local('mv ./pki/private/* {certs_dir}/'
                  .format(certs_dir=cls.KUBERNETES_CERTS_DIR))
            local('chown -R kube:kube {certs_dir}'
                  .format(certs_dir=cls.KUBERNETES_CERTS_DIR))
            local('chmod -R 0440 {certs_dir}/*'
                  .format(certs_dir=cls.KUBERNETES_CERTS_DIR))

        # upd.print_log("Updating apiserver config")
        helpers.update_local_config_file(
            "/etc/kubernetes/apiserver",
            {
                "KUBE_API_ARGS":
                    {
                        "--tls-cert-file=": cls.K8S_TLS_CERT,
                        "--tls-private-key-file=": cls.K8S_TLS_PRIVATE_KEY,
                        "--client-ca-file=": cls.K8S_CA_CERT,
                        "--service-account-key-file=": cls.K8S_TLS_CERT,
                    }
            }
        )
        # upd.print_log("Updating controller-manager config")
        helpers.update_local_config_file(
            "/etc/kubernetes/controller-manager",
            {
                "KUBE_CONTROLLER_MANAGER_ARGS":
                    {
                        "--service-account-private-key-file=": cls.K8S_TLS_PRIVATE_KEY,
                        "--root-ca-file=": cls.K8S_CA_CERT
                    }
            }
        )
        helpers.local('systemctl restart kube-apiserver', capture=False)

    @classmethod
    def downgrade(cls, upd, with_testing, exception, *args, **kwargs):
        # upd.print_log("Updating apiserver config")
        helpers.update_local_config_file(
            "/etc/kubernetes/apiserver",
            {
                "KUBE_API_ARGS":
                    {
                        "--tls-cert-file=": None,
                        "--tls-private-key-file=": None,
                        "--client-ca-file=": None,
                        "--service-account-key-file": None,
                    }
            }
        )
        # upd.print_log("Updating controller-manager config")
        helpers.update_local_config_file(
            "/etc/kubernetes/controller-manager",
            {
                "KUBE_CONTROLLER_MANAGER_ARGS":
                    {
                        "--service_account_private_key_file=": None,
                        "--root-ca-file=": None
                    }
            }
        )
        helpers.local('systemctl restart kube-apiserver', capture=False)


class _U182(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing, *args, **kwargs):
        # Such workaround needed only once because in previous version of KD we
        # have a bug with unclosed DB transactions which blocks upgrade
        upd.print_log('Stopping Kuberdock server to upgrade DB schema. '
                      'It will be restarted automatically upon '
                      'successful upgrade')
        helpers.local("systemctl stop emperor.uwsgi")

        upd.print_log('Upgrading schema...')
        helpers.upgrade_db(revision='8d3aed3e74c')

    @classmethod
    def downgrade(cls, upd, with_testing, exception, *args, **kwargs):
        upd.print_log('Downgrading schema...')
        helpers.downgrade_db(revision='12963e26b673')


class _U167Config(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing):
        helpers.update_local_config_file(
            '/etc/kubernetes/apiserver',
            {
                'KUBE_ADMISSION_CONTROL': {
                    '--admission-control=': 'NamespaceLifecycle,'
                                            'NamespaceExists,ServiceAccount',
                }
            }
        )
        helpers.local('systemctl restart kube-apiserver', capture=False)

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        helpers.update_local_config_file(
            '/etc/kubernetes/apiserver',
            {
                'KUBE_ADMISSION_CONTROL': {
                    '--admission-control=': 'NamespaceLifecycle,'
                                            'NamespaceExists',
                }
            }
        )
        helpers.local('systemctl restart kube-apiserver', capture=False)


class _U167Database(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing):
        try:
            from kubedock.domains.models import BaseDomain, PodDomain
        except ImportError:
            upd.print_log('Cannot find "domains" module related models')
        else:
            upd.print_log('Create table for BaseDomain model if not exists')
            BaseDomain.__table__.create(bind=db.engine, checkfirst=True)
            upd.print_log('Create table for PodDomain model if not exists')
            PodDomain.__table__.create(bind=db.engine, checkfirst=True)
            db.session.commit()

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        upd.print_log('DROP TABLE "pod_domains" IF EXISTS')
        table = Table('pod_domains', db.metadata)
        table.drop(bind=db.engine, checkfirst=True)
        upd.print_log('DROP TABLE "domains" IF EXISTS')
        table = Table('domains', db.metadata)
        table.drop(bind=db.engine, checkfirst=True)
        db.session.commit()


class _U167NetworkPlugin(_Update):
    PLUGIN_PATH = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'

    @classmethod
    def upgrade_node(cls, upd, with_testing, env):
        upd.print_log('Update network plugin...')
        run('ipset -exist create kuberdock_ingress hash:ip')
        put('/var/opt/kuberdock/node_network_plugin.sh',
            cls.PLUGIN_PATH + 'kuberdock')


class _U167Permissions(_Update):
    new_resources = ['domains']
    new_permissions = [
        ('domains', 'Admin', 'create', True),
        ('domains', 'Admin', 'get', True),
        ('domains', 'Admin', 'edit', True),
        ('domains', 'Admin', 'delete', True),
        ('domains', 'User', 'create', False),
        ('domains', 'User', 'get', True),
        ('domains', 'User', 'edit', False),
        ('domains', 'User', 'delete', False),
        ('domains', 'LimitedUser', 'create', False),
        ('domains', 'LimitedUser', 'get', True),
        ('domains', 'LimitedUser', 'edit', False),
        ('domains', 'LimitedUser', 'delete', False),
        ('domains', 'TrialUser', 'create', False),
        ('domains', 'TrialUser', 'get', True),
        ('domains', 'TrialUser', 'edit', False),
        ('domains', 'TrialUser', 'delete', False),
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


# noinspection SqlResolve
class _U167SystemSettings(_Update):
    NAMES = (
        'dns_management_system',
        'dns_management_cpanel_dnsonly_host',
        'dns_management_cpanel_dnsonly_user',
        'dns_management_cpanel_dnsonly_token',
    )

    @classmethod
    def upgrade(cls, upd, with_testing):
        for setting_name in cls.NAMES:
            SystemSettings.query.filter_by(name=setting_name).delete()
        db.session.commit()
        db.session.add_all([
            SystemSettings(
                name='dns_management_system',
                label='Select your DNS management system',
                value='cpanel_dnsonly',
            ),
            SystemSettings(
                name='dns_management_cpanel_dnsonly_host',
                label='cPanel URL for DNS management',
                description='cPanel URL that used for DNS management',
                placeholder='Enter URL for cPanel which serve your DNS '
                            'records',
            ),
            SystemSettings(
                name='dns_management_cpanel_dnsonly_user',
                label='cPanel user name for DNS management',
                description='cPanel user that used for DNS management auth',
                placeholder='Enter user for cPanel which serve your DNS '
                            'records',
            ),
            SystemSettings(
                name='dns_management_cpanel_dnsonly_token',
                label='cPanel user token for DNS management',
                description='cPanel token that used for DNS management auth',
                placeholder=(
                    'Enter token for cPanel which serve your DNS records'
                ),
                setting_group=None,
            ),
        ])
        db.session.commit()
        db.engine.execute("UPDATE system_settings SET setting_group='general'")
        db.engine.execute(
            "UPDATE system_settings SET setting_group='billing' "
            "WHERE name LIKE 'billing%%'")
        db.engine.execute(
            "UPDATE system_settings SET setting_group='domain' "
            "WHERE name LIKE 'dns%%'")
        db.engine.execute(
            """UPDATE system_settings SET """
            """options=('["No provider", "cpanel_dnsonly"]') WHERE id= 10""")
        db.engine.execute("UPDATE system_settings SET value='No provider' "
                          "WHERE id= 10")
        db.engine.execute(
            "UPDATE system_settings SET label='Select DNS provider' WHERE "
            "id= 10")
        db.engine.execute(
            "UPDATE system_settings SET label='Link to cPanel' WHERE id=11")
        db.engine.execute(
            "UPDATE system_settings SET placeholder='e.g. https://example.com'"
            "WHERE id=11")
        db.engine.execute(
            "UPDATE system_settings SET label='cPanel admin username' WHERE "
            "id=12")
        db.engine.execute(
            "UPDATE system_settings SET "
            "placeholder='user with rights to configure DNS zones' WHERE "
            "id=12")
        db.engine.execute(
            "UPDATE system_settings SET label='cPanel access key' WHERE id=13")
        db.engine.execute(
            "UPDATE system_settings SET "
            "placeholder='remote access key from cPanel' WHERE id=13")

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        for setting_name in cls.NAMES:
            SystemSettings.query.filter_by(name=setting_name).delete()
        db.session.commit()

        db.engine.execute("UPDATE system_settings SET options='' WHERE id=10")
        db.engine.execute("UPDATE system_settings SET value='' WHERE id=10")
        db.engine.execute(
            "UPDATE system_settings SET label"
            "='Select your DNS management system' WHERE id=10")
        db.engine.execute(
            "UPDATE system_settings SET label='cPanel URL for DNS management' "
            "WHERE id=11")
        db.engine.execute(
            "UPDATE system_settings SET "
            "placeholder='Enter URL for cPanel which serve your DNS records' "
            "WHERE id=11")
        db.engine.execute(
            "UPDATE system_settings SET "
            "label='cPanel user name for DNS management' WHERE id=12")
        db.engine.execute(
            "UPDATE system_settings SET "
            "placeholder='Enter user for cPanel which serve your DNS records' "
            "WHERE id=12")
        db.engine.execute(
            "UPDATE system_settings SET "
            "label='cPanel user token for DNS management' WHERE id=13")
        db.engine.execute(
            "UPDATE system_settings SET "
            "placeholder='Enter token for cPanel which serve your DNS records' "
            "WHERE id=13")


class _U171(_Update):
    RULE = "iptables -{} KUBERDOCK -t filter -p tcp --dport 25 -i docker0\
    -m set ! --match-set kuberdock_cluster dst -j REJECT"

    @classmethod
    def upgrade(cls, upd, with_testing):
        try:
            upd.print_log('Check if firewalld installed and running')
            subprocess.check_call(['rpm', '-q', 'firewalld'])
            subprocess.check_call(['firewall-cmd', '--state'])
        except subprocess.CalledProcessError:
            upd.print_log('Firewalld is not running, installing...')
            helpers.local("yum install -y firewalld")
            helpers.local("systemctl restart firewalld")
            helpers.local("systemctl reenable firewalld")

        upd.print_log('Adding Firewalld rules...')
        with quiet():
            helpers.local("rm -f /etc/firewalld/zones/public.xml")
            helpers.local("firewall-cmd --reload")
        firewall_rules = [
            "firewall-cmd --permanent --zone=public --add-port=80/tcp",
            "firewall-cmd --permanent --zone=public --add-port=443/tcp",
            "firewall-cmd --permanent --zone=public --add-port=123/udp",
            "firewall-cmd --permanent --zone=public --add-port=6443/tcp",
            "firewall-cmd --permanent --zone=public --add-port=2379/tcp",
            "firewall-cmd --permanent --zone=public --add-port=8123/tcp",
            "firewall-cmd --permanent --zone=public --add-port=8118/tcp",
            "firewall-cmd --reload",
        ]

        for rule in firewall_rules:
            helpers.local(rule)

    @classmethod
    def upgrade_node(cls, upd, with_testing, env, *args, **kwargs):
        upd.print_log('Reject outgoing smtp packets to 25 port')
        with quiet():
            put_rv = put('/var/opt/kuberdock/node_network_plugin.sh',
                         PLUGIN_PATH + 'kuberdock')
            if put_rv.failed:
                raise helpers.UpgradeError(
                    "Can't update node_network_plugin.sh")
            check = run(cls.RULE.format('C'))
            if check.return_code:
                rv = run(cls.RULE.format('I'))
                if rv.return_code:
                    raise helpers.UpgradeError(
                        "Can't add iptables rule: {}".format(rv))


class _U172(_Update):
    NEW_PERMISSIONS = [
        ('pods', 'Admin', 'dump', True),
        ('pods', 'LimitedUser', 'dump', False),
        ('pods', 'TrialUser', 'dump', False),
        ('pods', 'User', 'dump', False),
    ]

    @classmethod
    def upgrade(cls, upd, *args, **kwargs):
        upd.print_log('Upgrade permissions')
        rbac_fixtures._add_permissions(cls.NEW_PERMISSIONS)

    @classmethod
    def downgrade(cls, upd, *args, **kwargs):
        upd.print_log('Downgrade permissions')
        rbac_fixtures._delete_permissions(cls.NEW_PERMISSIONS)


class _U173(_Update):
    NAMES = ('email',)

    @classmethod
    def upgrade(cls, upd, with_testing):
        for setting_name in cls.NAMES:
            SystemSettings.query.filter_by(name=setting_name).delete()
        db.session.add_all([
            SystemSettings(
                name='email', label='Email for external services',
                setting_group='general',
                placeholder='Enter an email address',
                description=('Cluster-wide email that is required for cluster '
                             'authentication in external services.')),
        ])
        db.session.commit()

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        for setting_name in cls.NAMES:
            SystemSettings.query.filter_by(name=setting_name).delete()


class _U174(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing, *args, **kwargs):
        upd.print_log('Adding "Domains" to menus...')

        nav = Menu.query.filter_by(name='Navbar menu').one()
        role = Role.query.filter_by(rolename='Admin').one()
        adm = MenuItem.query.filter_by(name='Administration').one()
        item = MenuItem(name="Domains control", path="#domains", ordering=2)
        item.menu = nav
        item.parent = adm
        item.save()
        item_roles = MenuItemRole(role=role, menuitem=item)
        item_roles.save()

        if AWS:
            ippool = MenuItem.query.filter_by(name='IP pool').first()
            if ippool is not None:
                ippool.name = 'DNS names'
                ippool.save()
            public_ips = MenuItem.query.filter_by(name='Public IPs').first()
            if public_ips is not None:
                public_ips.name = 'Public DNS names'
                public_ips.save()

        db.session.commit()

    @classmethod
    def downgrade(cls, upd, with_testing, exception, *args, **kwargs):
        upd.print_log('Deleting "Domains" from menus...')

        item = MenuItem.query.filter_by(name='Domains control').first()
        if item is not None:
            item_role = MenuItemRole.query.filter_by(menuitem=item).one()
            item_role.delete()
            item.delete()
            db.session.commit()


class _U177(_Update):
    NEW_PERMISSIONS = [
        ('predefined_apps', 'LimitedUser', 'get', True),
        ('predefined_apps', 'TrialUser', 'get', True),
        ('predefined_apps', 'User', 'get', True),
    ]

    OLD_PERMISSIONS = [
        ('predefined_apps', 'LimitedUser', 'get', False),
        ('predefined_apps', 'TrialUser', 'get', False),
        ('predefined_apps', 'User', 'get', False),
    ]

    @classmethod
    def upgrade(cls, upd, with_testing, *args, **kwargs):
        upd.print_log('Upgrading permissions...')
        rbac_fixtures.change_permissions(cls.NEW_PERMISSIONS)

    @classmethod
    def downgrade(cls, upd, with_testing, exception, *args, **kwargs):
        upd.print_log('Downgrading permissions...')
        rbac_fixtures.change_permissions(cls.OLD_PERMISSIONS)


class _U178(_Update):
    @classmethod
    def upgrade_node(cls, upd, with_testing, *args, **kwargs):
        upd.print_log('Upgrading backup symlinks ...')

        put("/var/opt/kuberdock/backup_node.py", "/usr/bin/kd-backup-node")
        put("/var/opt/kuberdock/backup_node_merge.py",
            "/usr/bin/kd-backup-node-merge")

        run('chmod +x "/usr/bin/kd-backup-node-merge"')
        run('chmod +x "/usr/bin/kd-backup-node"')

    @classmethod
    def downgrade_node(cls, upd, with_testing, exception, *args, **kwargs):
        upd.print_log('Downgrading backup symlinks ...')

        run('rm "/usr/bin/kd-backup-node-merge"')
        run('rm "/usr/bin/kd-backup-node"')


class _U180(_Update):
    @classmethod
    def upgrade_node(cls, upd, with_testing, env, *args, **kwargs):
        upd.print_log('Update network plugin...')
        put('/var/opt/kuberdock/node_network_plugin.sh',
            PLUGIN_PATH + 'kuberdock')
        put('/var/opt/kuberdock/node_network_plugin.py',
            PLUGIN_PATH + 'kuberdock.py')


class _U184(_Update):
    NAMES = (
        keys.DNS_MANAGEMENT_ROUTE53_ID,
        keys.DNS_MANAGEMENT_ROUTE53_SECRET,
    )

    @classmethod
    def upgrade(cls, upd, with_testing, *args, **kwargs):
        for setting_name in cls.NAMES:
            SystemSettings.query.filter_by(name=setting_name).delete()
        db.session.add_all([
            SystemSettings(
                name=keys.DNS_MANAGEMENT_ROUTE53_ID,
                label='AWS Access Key ID',
                setting_group='domain',
                description='AWS Access Key ID for Route 53 DNS management',
                placeholder='Enter AWS Access Key ID'
            ),
            SystemSettings(
                name=keys.DNS_MANAGEMENT_ROUTE53_SECRET,
                label='AWS Secret Access Key',
                setting_group='domain',
                description='AWS Secret Access Key for Route 53 DNS management',
                placeholder='Enter AWS Secret Access Key'
            ),
        ])
        db.session.commit()


class _U188(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing):
        rbac_fixtures.change_permissions(rbac_fixtures.PERMISSIONS)


updates = [
    _U163,
    _U182,
    _U167Config,
    _U167Database,
    _U167NetworkPlugin,
    _U167Permissions,
    _U167SystemSettings,
    _U171,
    _U172,
    _U173,
    _U174,
    _U177,
    _U178,
    _U180,
    _U184,
    _U188,
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
