from fabric.operations import put, run

from kubedock.settings import NONFLOATING_PUBLIC_IPS, MASTER_IP
from kubedock.updates import helpers
from kubedock.users import User
from node_network_plugin import PLUGIN_PATH

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


def _upgrade_kubernetes(with_testing):
    helpers.remote_install(' '.join(KUBERNETES_PACKAGES), with_testing)
    service, res = helpers.restart_node_kubernetes()
    _raise_on_failure(service, res)


def _downgrade_kubernetes(with_testing):
    helpers.remote_install(' '.join(OLD_KUBERNETES_PACKAGES), with_testing,
                           action='downgrade')
    service, res = helpers.restart_node_kubernetes()
    _raise_on_failure(service, res)


def upgrade(upd, with_testing, *args, **kwargs):
    service, res = helpers.restart_master_kubernetes()
    _raise_on_failure(service, res)
    helpers.upgrade_db(revision='3dc83a81f385')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    service, res = helpers.restart_master_kubernetes()
    _raise_on_failure(service, res)
    helpers.downgrade_db(revision='3c832810a33c')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Upgrading kubernetes ...')
    _upgrade_kubernetes(with_testing)
    upd.print_log('Update network plugin...')
    put('/var/opt/kuberdock/node_network_plugin.sh', PLUGIN_PATH + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py',
        PLUGIN_PATH + 'kuberdock.py')
    token = User.get_internal().get_token()
    ini = KUBERDOCK_INI.format('yes' if NONFLOATING_PUBLIC_IPS else 'no',
                               MASTER_IP, env.host_string, token)
    run('echo "{0}" > "{1}"'.format(ini, PLUGIN_PATH + 'kuberdock.ini'))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Downgrading kubernetes ...')
    _downgrade_kubernetes(with_testing)


def _raise_on_failure(service, res):
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))
