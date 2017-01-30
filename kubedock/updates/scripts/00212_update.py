
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

import os
import re
from StringIO import StringIO
from time import sleep

import etcd
from fabric.api import local, run
from fabric.context_managers import shell_env
from fabric.operations import put, run

from kubedock import dns_management, settings
from kubedock.constants import (KUBERDOCK_BACKEND_POD_NAME,
                                KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
                                KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE,
                                KUBERDOCK_INGRESS_POD_NAME)
from kubedock.core import db
from kubedock.domains.models import BaseDomain, PodDomain
from kubedock.kapi import ingress, node_utils, nodes
from kubedock.kapi.configmap import ConfigMapClient, ConfigMapNotFound
from kubedock.kapi.helpers import KubeQuery
from kubedock.kapi.nodes import KUBERDOCK_DNS_POD_NAME, create_dns_pod
from kubedock.kapi.podcollection import PodCollection
from kubedock.network_policies_utils import create_network_policies
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod
from kubedock.rbac import fixtures as rbac_fixtures
from kubedock.system_settings import keys
from kubedock.system_settings.models import SystemSettings
from kubedock.updates import helpers
from kubedock.users.models import User, db
from kubedock.utils import NODE_STATUSES, get_hostname


####$################ BEGIN 194 update script #################################
"""Upgrade permissions for yaml_pods"""

new_permissions_194 = [
    ('yaml_pods', 'Admin', 'create_non_owned', True),
    ('yaml_pods', 'User', 'create_non_owned', False),
    ('yaml_pods', 'LimitedUser', 'create_non_owned', False),
    ('yaml_pods', 'TrialUser', 'create_non_owned', False),
]

def _upgrade_node_194(upd, with_testing, *args, **kwargs):
    pass


def _downgrade_node_194(upd, with_testing, *args, **kwargs):
    pass


def _upgrade_194(upd, *args, **kwargs):
    upd.print_log('Upgrade permissions')
    rbac_fixtures._add_permissions(new_permissions_194)


def _downgrade_194(upd, *args, **kwargs):
    upd.print_log('Downgrade permissions')
    rbac_fixtures._delete_permissions(new_permissions_194)

##################### END   193 update script #################################
####$################ BEGIN 195 update script #################################
def _upgrade_node_195(upd, with_testing, env, *args, **kwargs):
    pass


def _downgrade_node_195(upd, with_testing, env, *args, **kwargs):
   pass


def _upgrade_195(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='3e7a44cbe1e2')


def _downgrade_195(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db()

##################### END   193 update script #################################
####$################ BEGIN 197 update script #################################
def setting_by_name(name):
    return SystemSettings.query \
        .filter_by(name=name).first()


def _upgrade_node_197(upd, with_testing, env, *args, **kwargs):
    pass


def _downgrade_node_197(upd, with_testing, env, *args, **kwargs):
    pass


def _upgrade_197(upd, with_testing, *args, **kwargs):
    cpanel_host = setting_by_name(keys.DNS_MANAGEMENT_CPANEL_HOST)
    dns_management = setting_by_name(keys.DNS_MANAGEMENT_SYSTEM)
    if not cpanel_host.value and dns_management.value == 'cpanel_dnsonly':
        dns_management.value = 'No provider'
    dns_management.label = 'Select your DNS management system'
    cpanel_host.label = 'cPanel URL for DNS management'
    cpanel_host.placeholder = 'Enter URL for cPanel which serve your DNS ' \
                              'records'

    setting_by_name(keys.DNS_MANAGEMENT_CPANEL_USER) \
        .placeholder = 'Enter user for cPanel which serve your ' \
                       'DNS records'

    setting_by_name(keys.DNS_MANAGEMENT_CPANEL_TOKEN) \
        .placeholder = 'Enter token for cPanel which serve your ' \
                       'DNS records'

    setting_by_name(keys.BILLING_USERNAME).label = 'Billing admin username'
    setting_by_name(keys.BILLING_PASSWORD).label = 'Billing admin password'

    db.session.commit()

def _downgrade_197(upd, with_testing, exception, *args, **kwargs):
    pass

##################### END   197 update script #################################
####$################ BEGIN 199 update script #################################
def _upgrade_node_199(upd, with_testing, env, *args, **kwargs):
    pass


def _downgrade_node_199(upd, with_testing, env, *args, **kwargs):
    pass


def _upgrade_199(upd, with_testing, *args, **kwargs):
    ku = User.get_internal()
    pod = db.session.query(Pod).filter_by(
        name=KUBERDOCK_DNS_POD_NAME, owner=ku).first()
    nodes = Node.query.all()

    if not nodes:
        upd.print_log('No nodes found, exiting')
        return

    for node in nodes:
        k8s_node = node_utils._get_k8s_node_by_host(node.hostname)
        status, _ = node_utils.get_status(node, k8s_node)
        if status == NODE_STATUSES.running:
            if pod:
                pc = PodCollection()
                pc.delete(pod.id, force=True)
            create_dns_pod(node.hostname, ku)
            return

    raise helpers.UpgradeError("Can't find any running node to run dns pod")


def _downgrade_199(upd, with_testing,  exception, *args, **kwargs):
    pass

##################### END   199 update script #################################
####$################ BEGIN 202 update script #################################
RSYSLOG_CONF = '/etc/rsyslog.d/kuberdock.conf'

def _upgrade_node_202(upd, with_testing, env, *args, **kwargs):
    """Update log pod"""

    upd.print_log("Upgrading logs pod ...")
    ki = User.get_internal()
    pod_name = nodes.get_kuberdock_logs_pod_name(env.host_string)

    for pod in PodCollection(ki).get(as_json=False):
        if pod['name'] == pod_name:
            PodCollection(ki).delete(pod['id'], force=True)
            break
    else:
        upd.print_log(u"Warning: logs pod '{}' not found".format(pod_name))

    run('docker pull kuberdock/elasticsearch:2.2')
    run('docker pull kuberdock/fluentd:1.8')
    log_pod = nodes.create_logs_pod(env.host_string, ki)

    # Also we should update rsyslog config, because log pod IP was changed.
    pod_ip = log_pod['podIP']
    put(
        StringIO(
            '$LocalHostName {node_name}\n'
            '$template LongTagForwardFormat,'
            '"<%PRI%>%TIMESTAMP:::date-rfc3339% %HOSTNAME% '
            '%syslogtag%%msg:::sp-if-no-1st-sp%%msg%"\n'
            '*.* @{pod_ip}:5140;LongTagForwardFormat\n'.format(
                node_name=env.host_string, pod_ip=pod_ip
            )
        ),
        RSYSLOG_CONF,
        mode=0644
    )
    run('systemctl restart rsyslog')

    upd.print_log("Logs pod successfully upgraded")


def _downgrade_node_202(upd, with_testing, env, exception, *args, **kwargs):
    pass


def _upgrade_202(upd, with_testing, *args, **kwargs):
    pass


def _downgrade_202(upd, with_testing, exception, *args, **kwargs):
    pass


##################### END   202 update script #################################
##################### BEGIN 206 update script #################################
def _recreate_ingress_pod_if_needed():
    kd_user = User.get_internal()
    ingress_pod = Pod.filter_by(name=KUBERDOCK_INGRESS_POD_NAME,
                                owner=kd_user).first()
    if ingress_pod or BaseDomain.query.first():
        PodCollection(kd_user).delete(ingress_pod.id, force=True)
        default_backend_pod = Pod.filter_by(name=KUBERDOCK_BACKEND_POD_NAME,
                                            owner=kd_user).first()
        if not default_backend_pod:
            raise Exception(
                'Nginx ingress controller pod exists, but default backend pod '
                'is not found. Something wrong. Please contact support to get '
                'help.')
        PodCollection(kd_user).delete(default_backend_pod.id, force=True)
        c = ConfigMapClient(KubeQuery())
        try:
            c.delete(name=KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
                     namespace=KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE)
        except ConfigMapNotFound:
            pass
        sleep(30)  # TODO: Workaround. Remove it when AC-5470 will be fixed
        ingress.prepare_ip_sharing()


def _update_dns_records():
    record_type = 'CNAME' if settings.AWS else 'A'

    ingress_up = ingress.is_subsystem_up()

    for base_domain in BaseDomain.query.all():
        if not ingress_up:
            ingress.prepare_ip_sharing()
        domain = '*.{}'.format(base_domain.name)
        ok, message = dns_management.create_or_update_record(
            domain, record_type)
        if not ok:
            raise Exception(
                'Failed to create DNS record for domain "{domain}": {reason}'
                .format(domain=domain, reason=message))

    for pod_domain in PodDomain.query.all():
        domain = '{}.{}'.format(pod_domain.name, pod_domain.base_domain.name)
        ok, message = dns_management.delete_record(domain, record_type)
        if not ok:
            raise Exception(
                'Cannot delete old DNS record for domain "{domain}": {reason}'
                .format(domain=domain, reason=message))


def _upgrade_node_206(upd, with_testing, env, *args, **kwargs):
    pass


def _downgrade_node_206(upd, with_testing, env, *args, **kwargs):
    pass


def _upgrade_206(upd, *args, **kwargs):
    upd.print_log('Recreate ingress pod if needed...')
    _recreate_ingress_pod_if_needed()
    upd.print_log('Update dns records...')
    _update_dns_records()


def _downgrade_206(*args, **kwargs):
    pass

##################### END   206 update script #################################
####$################ BEGIN 210 update script #################################
KUBELET_CONFIG_FILE = '/etc/kubernetes/kubelet'

KPROXY_CONF = """\
[Unit]
After=network-online.target

[Service]
Restart=always
RestartSec=5s\
"""
KPROXY_SERVICE_DIR = "/etc/systemd/system/kube-proxy.service.d"


def _update_proxy_service(upd, func):
    upd.print_log('Enabling restart=always for kube-proxy.service')
    func('mkdir -p ' + KPROXY_SERVICE_DIR)
    func('echo -e "' + KPROXY_CONF + '" > ' + KPROXY_SERVICE_DIR + "/restart.conf")
    func('systemctl daemon-reload')
    func('systemctl restart kube-proxy')


def _upgrade_node_210(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Update kubelet config')
    helpers.update_remote_config_file(
        KUBELET_CONFIG_FILE,
        {
            'KUBELET_ARGS': {
                '--node-ip=': kwargs['node_ip'],
            }
        }
    )
    helpers.run('systemctl restart kubelet')
    # that's enough. IP address will be changed by kubernetes if needed

    _update_proxy_service(upd, run)


def _downgrade_node_210(*args, **kwargs):
    pass

def _upgrade_210(upd, *args, **kwargs):
    _update_proxy_service(upd, local)


def _downgrade_210(*args, **kwargs):
    pass
##################### END   210 update script #################################
####$################ BEGIN 212 update script #################################
K8S_VERSION = '1.2.4-7'
K8S = 'kubernetes-{name}-{version}.el7.cloudlinux'
K8S_NODE = K8S.format(name='node', version=K8S_VERSION)


def _upgrade_node_212(upd, with_testing, env, *args, **kwargs):
    upd.print_log("Upgrading kubernetes")
    helpers.remote_install(K8S_NODE, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError(
            'Failed to restart {0}. {1}'.format(service, res))


def _downgrade_node_212(upd, with_testing, env, exception, *args, **kwargs):
    pass

def _upgrade_212(upd, with_testing, *args, **kwargs):
    helpers.restart_master_kubernetes()

def _downgrade_212(upd, with_testing, exception, *args, **kwargs):
    pass
##################### END   212 update script #################################
####$################ BEGIN 213 update script #################################
"""AC-5478 Bump Docker Epoch"""
DOCKER_VERSION = '1.12.1-5.el7'
DOCKER = 'docker-{ver}'.format(ver=DOCKER_VERSION)
DOCKER_SELINUX = 'docker-selinux-{ver}'.format(ver=DOCKER_VERSION)

def _upgrade_node_213(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Updating Docker packages...')
    helpers.remote_install(DOCKER_SELINUX, with_testing)
    helpers.remote_install(DOCKER, with_testing)


def _downgrade_node_213(upd, with_testing, env, exception, *args, **kwargs):
    pass


def _upgrade_213(upd, with_testing, *args, **kwargs):
    # Docker on master upgraded via KuberDock package dependency
    pass


def _downgrade_213(upd, with_testing, exception, *args, **kwargs):
    pass
##################### END   213 update script #################################
####$################ BEGIN 214 update script #################################
"""AC-5571: Update Master hostname in Calico if it is wrong (short)"""

CALICO_NODE_IMAGE = 'kuberdock/calico-node:0.22.0-kd2'
MAX_RETRIES = 10
RETRY_PAUSE = 3


class _EtcdClient(object):
    CALICO_HOST_PATH = '/calico/ipam/v2/host/'

    def __init__(self, host, port):
        self._client = etcd.Client(host=host, port=port)

    def check_calico_host(self, host):
        try:
            self._client.read(self.CALICO_HOST_PATH + host)
        except etcd.EtcdKeyNotFound:
            return False
        return True


def _calicoctl_node(action, exc_message=None, upd=None, **env_vars):
    cmd = '/opt/bin/calicoctl node ' + action
    with shell_env(**dict(ETCD_AUTHORITY=settings.ETCD_AUTHORITY, **env_vars)):
        return helpers.fabric_retry(helpers.local, cmd,
                                    RETRY_PAUSE, MAX_RETRIES,
                                    exc_message=exc_message, upd=upd)


def _old_hostname():
    old_hostname_pattern = re.compile(
        'KUBE_API_ARGS.+?\s--tls-cert-file.+?/([^/]+?)\.crt\s'
    )
    with open('/etc/kubernetes/apiserver') as f:
        conf = f.read()
    match = old_hostname_pattern.search(conf)
    if match:
        return match.group(1)
    raise Exception("Old Master's hostname can't be determined")


def _upgrade_214(upd, with_testing, *args, **kwargs):
    new_hostname = get_hostname()
    old_hostname = _old_hostname()

    if new_hostname == old_hostname:
        return

    client = _EtcdClient(host=settings.ETCD_HOST, port=settings.ETCD_PORT)

    if client.check_calico_host(old_hostname):
        upd.print_log(
            'Remove previously registered Master from Calico: ' + old_hostname
        )
        _calicoctl_node('stop --force', upd=upd)
        _calicoctl_node(
            'remove --hostname={0} --remove-endpoints'.format(old_hostname),
            upd=upd,
        )

    if not client.check_calico_host(new_hostname):
        upd.print_log('Register Master in Calico: ' + new_hostname)
        _calicoctl_node(
            '--ip={0} --node-image={1}'.format(settings.MASTER_IP,
                                               CALICO_NODE_IMAGE),
            exc_message='Starting Calico node failed with: {out}',
            upd=upd,
            HOSTNAME=new_hostname,
        )

    upd.print_log('Updating network policies...')
    create_network_policies()


def _downgrade_214(upd, with_testing, exception, *args, **kwargs):
    pass


def _upgrade_node_214(upd, with_testing, env, *args, **kwargs):
    pass


def _downgrade_node_214(upd, with_testing, env, exception, *args, **kwargs):
    pass
##################### END   214 update script #################################
####$################ BEGIN 220 update script #################################
"""AC-5288 Update some node storage scripts"""

NODE_SCRIPT_DIR = '/var/lib/kuberdock/scripts'
NODE_STORAGE_MANAGE_DIR = 'node_storage_manage'
KD_INSTALL_DIR = '/var/opt/kuberdock'


def _upgrade_node_220(upd, with_testing, env, *args, **kwargs):
    target_script_dir = os.path.join(NODE_SCRIPT_DIR, NODE_STORAGE_MANAGE_DIR)
    scripts = ['aws.py', 'manage.py']
    for item in scripts:
        put(os.path.join(KD_INSTALL_DIR, NODE_STORAGE_MANAGE_DIR, item),
            os.path.join(target_script_dir, item))


def _downgrade_node_220(upd, with_testing, env, exception, *args, **kwargs):
    pass


def _upgrade_220(upd, with_testing, *args, **kwargs):
    pass


def _downgrade_220(upd, with_testing, exception, *args, **kwargs):
    pass
##################### END   220 update script #################################

updates = [
    195,
    194,
    197,
    199,
    202,
    206,
    210,
    212,
    213,
    214,
    220,
]


def _apply(method):
    def fn(*args, **kwargs):
        if method.startswith('down'):
            us = reversed(updates)
        else:
            us = updates

        for u in us:
            try:
                m = globals()['{}_{}'.format(method, u)]
            except KeyError:
                print('Missing {}_{} method'.format(method, u))
                continue
            m(*args, **kwargs)

    return fn


upgrade = _apply('_upgrade')
downgrade = _apply('_downgrade')
upgrade_node = _apply('_upgrade_node')
downgrade_node = _apply('_downgrade_node')
