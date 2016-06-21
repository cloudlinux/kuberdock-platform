import ConfigParser

from fabric.api import run
from kubedock.updates import helpers
from kubedock import settings

K8S_VERSION = '1.2.4-1'
K8S = 'kubernetes-{name}-{version}.el7.cloudlinux'
K8S_NODE = K8S.format(name='node', version=K8S_VERSION)
SA_KEY = "/etc/pki/kube-apiserver/serviceaccount.key"

ETCD_VERSION = '2.2.5'
ETCD = 'etcd-{version}'.format(version=ETCD_VERSION)
ETCD_SERVICE_FILE = '/etc/systemd/system/etcd.service'


# NOTE(lobur): this script should came one of the first in the 1.3.0 upgrade
# When upgrade is started it installs the new k8s & etcd on master (via rpm
# dependency) This script then updates configs and node k8s version to match
# the new master. Until that cluster is not alive, that's why it should be
# at the beginning.


class NonTransformConfigParser(ConfigParser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr


def _upgrade_etcd(upd):
    upd.print_log('Upgrading etcd...')
    cp = NonTransformConfigParser()
    with open(ETCD_SERVICE_FILE) as f:
        cp.readfp(f)

    cp.set('Service', 'Type', 'notify')
    with open(ETCD_SERVICE_FILE, "w") as f:
        cp.write(f)

    helpers.local('systemctl daemon-reload', capture=False)
    helpers.local('systemctl restart etcd', capture=False)


def _downgrade_etcd(upd):
    upd.print_log('Downgrading etcd...')
    cp = NonTransformConfigParser()
    with open(ETCD_SERVICE_FILE) as f:
        cp.readfp(f)

    cp.set('Service', 'Type', 'simple')
    with open(ETCD_SERVICE_FILE, "w") as f:
        cp.write(f)

    helpers.local('systemctl daemon-reload', capture=False)
    helpers.local('systemctl restart etcd', capture=False)


def _upgrade_k8s_master(upd, with_testing):
    # ServiceAccount signing key
    upd.print_log("Generating key for service account")
    helpers.local("""
mkdir -m o-rwx -p `dirname {key}`
openssl genrsa -out {key} 2048
chmod -R 0440 {key}
chown -R kube:kube `dirname {key}`
""".format(key=SA_KEY))

    upd.print_log("Updating apiserver config")
    helpers.update_local_config_file(
        "/etc/kubernetes/apiserver",
        {
            "KUBE_API_ARGS":
                {"--service_account_key_file=": SA_KEY}
        }
    )
    helpers.update_local_config_file(
        "/etc/kubernetes/apiserver",
        {
            "KUBE_ADMISSION_CONTROL":
                {"--admission_control=": "NamespaceLifecycle,NamespaceExists"}}
    )

    upd.print_log("Updating controller-manager config")
    helpers.update_local_config_file(
        "/etc/kubernetes/controller-manager",
        {
            "KUBE_CONTROLLER_MANAGER_ARGS":
                {"--service_account_private_key_file=": SA_KEY}
        }
    )


def _downgrade_k8s_master(upd, with_testing):
    upd.print_log("Removing service account key.")
    helpers.local('rm -rf `dirname %s`' % SA_KEY)

    upd.print_log("Updating apiserver config")
    helpers.update_local_config_file(
        '/etc/kubernetes/apiserver',
        {
            "KUBE_API_ARGS":
                {"--service_account_key_file=": None}
        }
    )

    helpers.update_local_config_file(
        "/etc/kubernetes/apiserver",
        {
            "KUBE_ADMISSION_CONTROL":
                {
                    "--admission_control=":
                        "NamespaceLifecycle,"
                        "NamespaceExists,"
                        "SecurityContextDeny"
                }
        }
    )

    upd.print_log("Updating controller-manager config")
    helpers.update_local_config_file(
        '/etc/kubernetes/controller-manager',
        {
            "KUBE_CONTROLLER_MANAGER_ARGS":
                {"--service_account_private_key_file=": None}
        }
    )


def _upgrade_k8s_node(upd, with_testing):
    upd.print_log("Upgrading kubernetes")
    helpers.remote_install(K8S_NODE, with_testing)
    upd.print_log("Updating kubelet config")
    run("sed -i '/^KUBELET_HOSTNAME/s/^/#/' /etc/kubernetes/kubelet")
    run("sed -i '/^KUBE_PROXY_ARGS/ {s|--kubeconfig=/etc/kubernetes/configfile|"
        "--kubeconfig=/etc/kubernetes/configfile --proxy-mode userspace|}' /etc/kubernetes/proxy")


def _downgrade_k8s_node(upd, with_testing):
    upd.print_log("Downgrading kubernetes")
    helpers.remote_install('kubernetes-node kubernetes-client', with_testing, action='downgrade')
    upd.print_log("Updating kubelet config")
    run("sed -i '/^#KUBELET_HOSTNAME/s/^#//' /etc/kubernetes/kubelet")
    run("sed -i '/^KUBE_PROXY_ARGS/ {s|--proxy-mode userspace||}' /etc/kubernetes/proxy")


def upgrade(upd, with_testing, *args, **kwargs):
    _upgrade_k8s_master(upd, with_testing)
    service, res = helpers.restart_master_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))

    _upgrade_etcd(upd)

    # Restart KD to make sure new libs are running
    res = helpers.restart_service(settings.KUBERDOCK_SERVICE)
    if res != 0:
        raise helpers.UpgradeError('Failed to restart KuberDock')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    _downgrade_k8s_master(upd, with_testing)
    service, res = helpers.restart_master_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))

    _downgrade_etcd(upd)

    # Restart KD to make sure new libs are running
    res = helpers.restart_service(settings.KUBERDOCK_SERVICE)
    if res != 0:
        raise helpers.UpgradeError('Failed to restart KuberDock')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _upgrade_k8s_node(upd, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    _downgrade_k8s_node(upd, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))
