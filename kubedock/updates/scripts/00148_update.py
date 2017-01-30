
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import ConfigParser
import copy
import json
from StringIO import StringIO

from fabric.operations import put, run

from kubedock import settings
from kubedock.kapi import helpers as kapi_helpers
from kubedock.kapi.podcollection import PodCollection
from kubedock.pods import Pod
from kubedock.updates import helpers
from kubedock.users import User
from kubedock.utils import POD_STATUSES
from node_network_plugin import PLUGIN_PATH, KD_CONF_PATH

K8S_VERSION = '1.2.4-2'
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


def _update_node_network_plugin(upd, env):
    upd.print_log('Update network plugin...')
    put('/var/opt/kuberdock/node_network_plugin.sh',
        PLUGIN_PATH + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py',
        PLUGIN_PATH + 'kuberdock.py')

    kd_conf = {
        'nonfloating_public_ips':
            'yes' if settings.NONFLOATING_PUBLIC_IPS else 'no',
        'master': settings.MASTER_IP,
        'node': env.host_string,
        'token': User.get_internal().get_token()
    }
    put(StringIO(json.dumps(kd_conf)), KD_CONF_PATH)


def _update_pv_mount_paths(upd):
    """Migration k8s 1.1.3 -> 1.2.4 requires removing :Z from mount paths"""
    # Patch RC specs
    upd.print_log("Updating Pod PV mount paths")

    def remove_trailing_z(pod_config):
        updated_config = copy.deepcopy(pod_config)
        for container in updated_config['containers']:
            for mount in container['volumeMounts']:
                mp = mount['mountPath']
                if mp.endswith(":z") or mp.endswith(":Z"):
                    mount['mountPath'] = mount['mountPath'][:-2]
        return updated_config

    pc = PodCollection()
    query = Pod.query.filter(Pod.status != POD_STATUSES.deleted)
    for dbpod in query:
        updated_config = remove_trailing_z(dbpod.get_dbconfig())

        # Update config
        kapi_helpers.replace_pod_config(dbpod, updated_config)
        pc.patch_running_pod(dbpod.id, {'spec': updated_config}, restart=True)

        upd.print_log(u'Successfully updated pod: {}'.format(dbpod.name))


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

    helpers.upgrade_db()
    _update_pv_mount_paths(upd)


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
    helpers.downgrade_db(revision='3c832810a33c')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _upgrade_k8s_node(upd, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))

    _update_node_network_plugin(upd, env)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    _downgrade_k8s_node(upd, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))
