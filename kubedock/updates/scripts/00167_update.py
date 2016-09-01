from abc import ABCMeta

from fabric.operations import put, run
from sqlalchemy import Table

from kubedock.core import db
from kubedock.rbac import fixtures as rbac_fixtures
from kubedock.system_settings.models import SystemSettings
from kubedock.updates import helpers


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
        upd.print_log('Drop table "pod_domains" if exists')
        table = Table('pod_domains', db.metadata)
        table.drop(bind=db.engine, checkfirst=True)
        upd.print_log('Drop table "domains" if exists')
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
        ('domains', 'User', 'get', True),
        ('domains', 'LimitedUser', 'get', True),
        ('domains', 'TrialUser', 'get', True),
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

    @classmethod
    def downgrade(cls, upd, with_testing, error):
        for setting_name in cls.NAMES:
            SystemSettings.query.filter_by(name=setting_name).delete()


class _U182(_Update):
    @classmethod
    def upgrade(cls, upd, with_testing, *args, **kwargs):
        upd.print_log('Upgrading schema...')
        helpers.upgrade_db(revision='8d3aed3e74c')

    @classmethod
    def downgrade(cls, upd, with_testing, exception, *args, **kwargs):
        upd.print_log('Downgrading schema...')
        helpers.downgrade_db(revision='12963e26b673')


updates = [
    _U167Config,
    _U167Database,
    _U167NetworkPlugin,
    _U167Permissions,
    _U182,
    _U167SystemSettings,
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
