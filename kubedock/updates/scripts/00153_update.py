import ConfigParser
from fabric.api import run
from kubedock.kapi.nodes import get_dns_pod_config, get_dns_pod_config_pre_k8s_1_2
from kubedock.settings import KUBERDOCK_INTERNAL_USER
from kubedock.kapi.podcollection import PodCollection
from kubedock.users.models import User
from kubedock.pods.models import Pod
from kubedock.validation import check_internal_pod_data

from kubedock.updates import helpers

ETCD_VERSION = '2.2.5'
ETCD = 'etcd-{version}'.format(version=ETCD_VERSION)
ETCD_SERVICE_FILE = '/etc/systemd/system/etcd.service'

K8S_VERSION = '1.2.4-1'
K8S = 'kubernetes-{name}-{version}.el7.cloudlinux'
K8S_NODE = K8S.format(name='node', version=K8S_VERSION)
SA_KEY="/etc/pki/kube-apiserver/serviceaccount.key"


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


def _recreate_dns_pod(dns_pod_config):
    user = User.filter_by(username=KUBERDOCK_INTERNAL_USER).one()
    dns_pod = Pod.filter_by(name='kuberdock-dns', owner=user).first()
    if dns_pod:
        PodCollection(user).delete(dns_pod.id, force=True)

    check_internal_pod_data(dns_pod_config, user)
    dns_pod = PodCollection(user).add(dns_pod_config, skip_check=True)
    PodCollection(user).update(dns_pod['id'], {'command': 'start'})


def _upgrade_dns_pod(upd):
    upd.print_log('Upgrading DNS pod...')
    dns_pod_config = get_dns_pod_config()
    _recreate_dns_pod(dns_pod_config)


def _downgrade_dns_pod(upd):
    upd.print_log('Downgrading DNS pod...')
    dns_pod_config = get_dns_pod_config_pre_k8s_1_2()
    _recreate_dns_pod(dns_pod_config)


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
    helpers.update_local_config_file("/etc/kubernetes/apiserver",
                                     {"KUBE_API_ARGS": {"--service_account_key_file=": SA_KEY}})

    upd.print_log("Updating controller-manager config")
    helpers.update_local_config_file("/etc/kubernetes/controller-manager",
                                     {"KUBE_CONTROLLER_MANAGER_ARGS": {"--service_account_private_key_file=": SA_KEY}})
    _upgrade_dns_pod(upd)


def _downgrade_k8s_master(upd, with_testing):
    upd.print_log("Removing service account key.")
    helpers.local('rm -rf `dirname %s`' % SA_KEY)

    upd.print_log("Updating apiserver config")
    helpers.update_local_config_file('/etc/kubernetes/apiserver',
                                     {"KUBE_API_ARGS": {"--service_account_key_file=": None}})

    upd.print_log("Updating controller-manager config")
    helpers.update_local_config_file('/etc/kubernetes/controller-manager',
                                     {"KUBE_CONTROLLER_MANAGER_ARGS": {"--service_account_private_key_file=": None}})
    _downgrade_dns_pod(upd)


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
    _upgrade_etcd()
    _upgrade_k8s_master(upd, with_testing)
    service, res = helpers.restart_master_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))


def downgrade(upd, with_testing, exception, *args, **kwargs):
    _downgrade_etcd()
    _downgrade_k8s_master(upd, with_testing)
    service, res = helpers.restart_master_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _upgrade_k8s_node(upd, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    _upgrade_k8s_node(upd, with_testing)
    helpers.restart_node_kubernetes()
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))
