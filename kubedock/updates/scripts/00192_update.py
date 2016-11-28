import json
import os
import re
import socket
import ConfigParser
from StringIO import StringIO

from itertools import chain
import yaml
from fabric.operations import run, get, put
from fabric.context_managers import cd, quiet

from kubedock.allowed_ports.models import AllowedPort
from kubedock.core import db, ssh_connect
from kubedock.domains.models import BaseDomain, PodDomain
from kubedock.exceptions import DomainNotFound
from kubedock.kapi.nodes import (
    KUBERDOCK_DNS_POD_NAME,
    create_policy_pod,
    get_dns_policy_config,
    get_node_token,
)
from kubedock.kapi import podcollection, restricted_ports
from kubedock.kapi.pstorage import CephStorage, get_ceph_credentials
from kubedock.kapi.helpers import (
    KUBERDOCK_POD_UID,
    KUBERDOCK_TYPE,
    LOCAL_SVC_TYPE,
    Services,
    replace_pod_config,
)
from kubedock.kapi.node_utils import complete_calico_node_config
from kubedock.kapi.nodes import get_kuberdock_logs_pod_name
from kubedock.kapi.podutils import raise_if_failure
from kubedock.kapi.podcollection import PodCollection, PodNotFound, \
    run_service, PublicAccessType
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod
from kubedock.predefined_apps.models import PredefinedApp
from kubedock.rbac import fixtures
from kubedock.restricted_ports.models import RestrictedPort
from kubedock.settings import (
    ETCD_NETWORK_POLICY_SERVICE,
    MASTER_IP, NODE_DATA_DIR, NODE_TOBIND_EXTERNAL_IPS
)
from kubedock import settings
from kubedock.system_settings import keys
from kubedock.system_settings.models import SystemSettings
from kubedock.updates import helpers
from kubedock.users.models import User
from kubedock.utils import (
    POD_STATUSES, Etcd, get_calico_ip_tunnel_address, retry)


KUBERDOCK_MAIN_CONFIG = '/etc/sysconfig/kuberdock/kuberdock.conf'

# It is needed for upgraded kube-proxy
CONNTRACK_PACKAGE = 'conntrack-tools'

# update 00174
K8S_VERSION = '1.2.4-6'
K8S = 'kubernetes-{name}-{version}.el7.cloudlinux'
K8S_NODE = K8S.format(name='node', version=K8S_VERSION)

# update 00179
RSYSLOG_CONF = '/etc/rsyslog.d/kuberdock.conf'

# update 00186
NAMES = (
    keys.DNS_MANAGEMENT_CLOUDFLARE_EMAIL,
    keys.DNS_MANAGEMENT_CLOUDFLARE_TOKEN,
)

# update 00188 (00187)
NODE_SCRIPT_DIR = '/var/lib/kuberdock/scripts'
NODE_STORAGE_MANAGE_DIR = 'node_storage_manage'
KD_INSTALL_DIR = '/var/opt/kuberdock'

# update 00197
new_resources = [
    'allowed-ports',
]

new_permissions = [
    ('allowed-ports', 'Admin', 'get', True),
    ('allowed-ports', 'Admin', 'create', True),
    ('allowed-ports', 'Admin', 'delete', True),
]

# update 00201
new_resources = [
    'restricted-ports',
]

new_permissions = [
    ('restricted-ports', 'Admin', 'get', True),
    ('restricted-ports', 'Admin', 'create', True),
    ('restricted-ports', 'Admin', 'delete', True),
]


def _add_public_access_type(upd):
    upd.print_log('Update pod configs')
    pods = Pod.all()
    for pod in pods:
        db_config = pod.get_dbconfig()
        pod.set_dbconfig(db_config, save=False)

        if 'public_access_type' in db_config:
            continue

        elif (db_config.get('public_ip', None)
                or db_config.get('public_ip_before_freed', None)):
            db_config['public_access_type'] = PublicAccessType.PUBLIC_IP

        elif db_config.get('public_aws', None):
            db_config['public_access_type'] = PublicAccessType.PUBLIC_AWS

        elif db_config.get('domain', None):
            db_config['public_access_type'] = PublicAccessType.DOMAIN

            if not db_config.get('base_domain', None):
                domain = db_config['domain']

                base_domain = BaseDomain.query.filter_by(name=domain).first()

                if base_domain:
                    db_config['base_domain'] = domain
                    db_config.pop('domain')

                else:
                    sub_domain_part, base_domain_part = domain.split('.', 1)

                    base_domain = BaseDomain.query.filter_by(
                        name=base_domain_part).first()

                    if base_domain is None:
                        raise DomainNotFound(
                            "Can't find BaseDomain for requested domain {0}"
                            .format(domain)
                        )

                    pod_domain = PodDomain.query.filter_by(
                        name=sub_domain_part, domain_id=base_domain.id,
                        pod_id=pod.id
                    ).first()

                    if not pod_domain:
                        raise DomainNotFound(
                            "Can't find PodDomain for requested domain {0}"
                            .format(domain)
                        )

                    db_config['base_domain'] = base_domain.name
                    db_config['domain'] = domain

        else:
            db_config['public_access_type'] = PublicAccessType.PUBLIC_IP

        pod.set_dbconfig(db_config, save=False)


def _update_nonfloating_config(upd):
    upd.print_log('Updating kube-scheduler config...')
    helpers.local('sed -i "s/--enable-non-floating-ip/--enable-fixed-ip-pools/" /etc/kubernetes/scheduler')
    helpers.local('systemctl restart kube-scheduler')
    upd.print_log('Updating kuberdock main config...')
    helpers.local('sed -i "s/NONFLOATING_PUBLIC_IPS/FIXED_IP_POOLS/" {}'.format(KUBERDOCK_MAIN_CONFIG))


def _update_node_nonfloating_config(upd):
    # it should be called before _update_00191_upgrade_node
    upd.print_log('Updating kuberdock.json')
    config_file = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/kuberdock.json'
    run('sed -i "s/nonfloating_public_ips/fixed_ip_pools/" {}'.format(config_file))


def _update_00200_upgrade(upd):  # also applies 00196 update migration
    upd.print_log('Upgrading db...')
    helpers.upgrade_db()


def _update_00174_upgrade_node(upd, with_testing):
    upd.print_log("Upgrading kubernetes")
    helpers.remote_install(K8S_NODE, with_testing)
    service, res = helpers.restart_node_kubernetes()
    if res != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))


def _update_00176_upgrade(upd):
    pas_to_upgrade = {
        pa.id: pa for pa in PredefinedApp.query.all()
        if _pa_contains_originroot_hack(pa)}

    if not pas_to_upgrade:
        upd.print_log('No outdated PAs. Skipping')
        return

    pods_to_upgrade = Pod.query.filter(
        Pod.template_id.in_(pas_to_upgrade.keys())).all()

    _remove_lifecycle_section_from_pods(upd, pods_to_upgrade, pas_to_upgrade)
    _update_predefined_apps(upd, pas_to_upgrade)
    _mark_volumes_as_prefilled(pas_to_upgrade, pods_to_upgrade)


def _update_00176_upgrade_node(upd, with_testing):
    _node_flannel()
    # Moved flannel removal before docker upgrade because else docker will reuse
    # old flannel IP 10.254.*.* (use one from docker0 iface) and save it to
    # config /var/lib/docker/network/files/local-kv.db
    run('sync')
    run("systemctl stop docker && ip link del docker0")
    _upgrade_docker(upd, with_testing)


def _update_00179_upgrade_node(env):
    nodename = env.host_string
    log_pod_name = get_kuberdock_logs_pod_name(nodename)
    internal_user = User.get_internal()
    pc = PodCollection(internal_user)
    dbpod = Pod.query.filter(
        Pod.owner_id == internal_user.id, Pod.name == log_pod_name,
        Pod.status != 'deleted').first()
    if not dbpod:
        raise Exception('Node {} have no logs pod. '
                        'Delete the node and try again'.format(nodename))
    pod = pc.get(dbpod.id, as_json=False)
    old_ip = '127.0.0.1'
    new_ip = pod['podIP']
    run('sed -i "s/@{old_ip}:/@{new_ip}:/g" {conf}'.format(
        old_ip=old_ip, new_ip=new_ip, conf=RSYSLOG_CONF))
    run('systemctl restart rsyslog')


def _update_00185_upgrade():
    SystemSettings.query.filter_by(name=keys.MAX_KUBES_TRIAL_USER).delete()
    db.session.add_all([
        SystemSettings(
            name=keys.MAX_KUBES_TRIAL_USER, value='5',
            label='Kubes limit for Trial user',
            placeholder='Enter Kubes limit for Trial user',
            setting_group='general'
        ),
    ])
    db.session.commit()


def _update_00186_upgrade():
    for setting_name in NAMES:
        SystemSettings.query.filter_by(name=setting_name).delete()
    db.session.add_all([
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CLOUDFLARE_EMAIL,
            label='CloudFlare Email',
            description='Email for CloudFlare DNS management',
            placeholder='Enter CloudFlare Email',
            setting_group='domain'
        ),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CLOUDFLARE_TOKEN,
            label='CloudFlare Global API Key',
            description='Global API Key for CloudFlare DNS management',
            placeholder='Enter CloudFlare Global API Key',
            setting_group='domain'
        ),
    ])
    db.session.commit()


def _update_00188_upgrade_node():  # update 00187 absorbed by 00188
    target_script_dir = os.path.join(NODE_SCRIPT_DIR, NODE_STORAGE_MANAGE_DIR)
    run('mkdir -p ' + target_script_dir)
    scripts = [
        'aws.py', 'common.py', '__init__.py', 'manage.py',
        'node_lvm_manage.py', 'node_zfs_manage.py'
    ]
    for item in scripts:
        put(os.path.join(KD_INSTALL_DIR, NODE_STORAGE_MANAGE_DIR, item),
            target_script_dir)
    # Update symlink only if it not exists
    with cd(target_script_dir):
        run('ln -s node_lvm_manage.py storage.py 2> /dev/null || true')


def _update_00191_upgrade(upd, calico_network):
    _master_flannel()

    etcd1 = helpers.local('uname -n')
    _master_etcd_cert(etcd1)
    _master_etcd_conf(etcd1)
    helpers.restart_service('etcd')

    _master_docker(upd)
    _master_firewalld()
    _master_k8s_node()

    if helpers.local('docker ps --format "{{.Names}}" | grep "^calico-node$"') != 'calico-node':
        _master_calico(upd, calico_network)

    _master_k8s_extensions()
    helpers.restart_master_kubernetes()
    helpers.local('echo "{0}" | kubectl create -f -'.format(_K8S_EXTENSIONS))
    # we need to restart here again, because kubernetes sometimes don't accept
    # extensions onfly
    helpers.restart_master_kubernetes()
    _master_network_policy(upd, calico_network)

    _master_dns_policy()
    _master_pods_policy()

    _master_service_update()


def _update_00191_upgrade_node(upd, with_testing, env, **kwargs):
    helpers.remote_install(CONNTRACK_PACKAGE)
    _node_kube_proxy()

    if run('docker ps --format "{{.Names}}" | grep "^calico-node$"') != 'calico-node':
        _node_calico(upd, with_testing, env.host_string, kwargs['node_ip'])

    _node_policy_agent(env.host_string)
    _node_move_config()


def _update_00191_post_upgrade_nodes():
    _add_nodes_host_endpoints()


def _update_00197_upgrade(upd):
    upd.print_log('Create table for AllowedPort model if not exists')
    AllowedPort.__table__.create(bind=db.engine, checkfirst=True)
    upd.print_log('Upgrade permissions')
    fixtures.add_permissions(resources=new_resources,
                             permissions=new_permissions)


def _update_00201_upgrade(upd):
    upd.print_log('Create table for RestrictedPort model if not exists')
    RestrictedPort.__table__.create(bind=db.engine, checkfirst=True)
    upd.print_log('Upgrade permissions')
    fixtures.add_permissions(resources=new_resources,
                             permissions=new_permissions)
    upd.print_log('reject outgoing not authorized smtp packets '
                  'to prevent spamming from containers')
    try:
        restricted_ports.del_port(25, 'tcp')
    except restricted_ports.RestrictedPortsException.OpenPortError:
        pass
    finally:
        restricted_ports.set_port(25, 'tcp')



# update 00176 stuff bellow (update 00175 absorbed by 00176)

DOCKER_VERSION = '1.12.1-4.el7'
DOCKER = 'docker-{ver}'.format(ver=DOCKER_VERSION)
SELINUX = 'docker-selinux-{ver}'.format(ver=DOCKER_VERSION)


def _upgrade_docker(upd, with_testing):
    def alter_config(line):
        if not re.match(r'OPTIONS=.*', line):
            return line

        to_remove = (r'\s*(--log-level=[^\s\']+\s*)|(-l \[^\s\']+\s*)',
                     r'\s*(--log-driver=[^\s\']+)')
        for pattern in to_remove:
            line = re.sub(pattern, '', line)

        return re.sub(r"OPTIONS='(.*)'",
                      r"OPTIONS='\1 --log-driver=json-file --log-level=error'",
                      line)

    helpers.remote_install(SELINUX, with_testing)
    helpers.remote_install(DOCKER, with_testing)

    docker_config = StringIO()
    get('/etc/sysconfig/docker', docker_config)
    current_config = docker_config.getvalue()
    new_config = '\n'.join(alter_config(l) for l in current_config.splitlines())

    run("cat << EOF > /etc/sysconfig/docker\n{}\nEOF".format(new_config))

    # If we restart docker here then rest of node upgrade code will be
    # executed with fresh new docker (don't know whether this is good or bad)
    # and also will results in pods/containers restart at this moment, which
    # will produce lots of events and load on node.
    # If not, then docker will be old till node reboot at the end of upgrade.
    # So we probably could comment restart part (known to work ~ok)
    run("systemctl daemon-reload")
    res = run("systemctl restart docker")
    if res.failed:
        raise helpers.UpgradeError('Failed to restart docker. {}'.format(res))
    upd.print_log(run("docker --version"))


def contains_origin_root(container):
    try:
        return '/originroot/' in str(
            container['lifecycle']['postStart']['exec']['command'])
    except KeyError:
        return False


def _pa_contains_originroot_hack(app):
    tpl = yaml.load(app.template)
    try:
        containers = tpl['spec']['template']['spec']['containers']
    except KeyError:
        return False

    return any(contains_origin_root(c) for c in containers)


def _remove_lifecycle_section_from_pods(upd, pods, pas):
    # PodCollection.update({'command': 'change_config'}) can't delete keys
    # thus mocking instead
    def _mock_lifecycle(config):
        for container in config['containers']:
            if not contains_origin_root(container):
                continue
            container['lifecycle'] = {
                'postStart': {'exec': {'command': ['/bin/true']}}
            }
        return config

    def _set_prefill_flag(config, pod):
        prefilled_volumes = _extract_prefilled_volumes_from_pod(pas, pod)

        for container in config['containers']:
            for vm in container.get('volumeMounts', []):
                if vm['name'] in prefilled_volumes:
                    vm['kdCopyFromImage'] = True

    collection = PodCollection()

    for pod in pods:
        config = _mock_lifecycle(pod.get_dbconfig())
        _set_prefill_flag(config, pod)
        config['command'] = 'change_config'

        try:
            replace_pod_config(pod, config)
            collection.update(pod.id, config)
            upd.print_log('POD {} config patched'.format(pod.id))
        except PodNotFound:
            upd.print_log('Skipping POD {}. Not found in K8S'.format(pod.id))


def _connect_or_raise(host):
    ssh, err = ssh_connect(host)
    if err:
        raise Exception(err)
    return ssh


def _get_mapped_ceph_devices(ssh):
    _, o, _ = ssh.exec_command(
        'rbd {} showmapped --format=json'.format(get_ceph_credentials()))

    data = {
        '{}/{}'.format(v['pool'], v['name']): v['device']
        for v in json.loads(o.read()).values()
    }

    return data


def _mark_ceph_storage_as_prefilled(storage, volumes):
    ssh = _connect_or_raise(storage.get_node_ip())

    temp_dir = ssh.exec_command('mktemp -d')[1].read().strip()
    lock_path = os.path.join(temp_dir, '.kd_prefill_succeded')
    mapped_devices = _get_mapped_ceph_devices(ssh)

    for rbd in volumes:
        block_device = mapped_devices.get(rbd, storage._map_drive(rbd))

        commands = [
            'mount {} {}'.format(block_device, temp_dir),
            'touch {}'.format(lock_path),
            'umount {}'.format(temp_dir),
        ]

        try:
            for c in commands:
                i, o, e = ssh.exec_command(c)
                exit_status = o.channel.recv_exit_status()
                if exit_status != 0:
                    raise Exception(e.read())
        finally:
            if rbd not in mapped_devices:
                storage._unmap_drive(block_device)


def _mark_volumes_as_prefilled(pas, pods):
    # Declare it here to cache the "first node"
    storage = CephStorage()

    for pod in pods:
        prefilled_volumes = _extract_prefilled_volumes_from_pod(pas, pod)
        config = pod.get_dbconfig()

        volumes = [v for v in config['volumes'] if v['name'] in prefilled_volumes]

        if settings.CEPH:
            drives = [
                '{}/{}'.format(v['rbd']['pool'], v['rbd']['image'])
                for v in volumes]

            _mark_ceph_storage_as_prefilled(storage, drives)
        else:
            ssh = _connect_or_raise(pod.pinned_node)

            for path in (v['hostPath']['path'] for v in volumes):
                lock_path = os.path.join(path, '.kd_prefill_succeded')
                ssh.exec_command('touch {}'.format(lock_path))


def _extract_prefilled_volumes_from_pod(pas, pod):
    template = yaml.load(pas[pod.template_id].template)
    containers = (c for c in
                  template['spec']['template']['spec']['containers'])
    return {vm['name'] for c in containers for vm in c['volumeMounts']}


def _update_predefined_apps(upd, kd_pas):
    for pa in kd_pas.values():
        template = yaml.load(pa.template)

        try:
            containers = template['spec']['template']['spec']['containers']
        except KeyError:
            upd.print_log('Unexpected PA {} found. Skipping'.format(pa.id))
            continue

        for container in containers:
            container.pop('lifecycle', None)
            for mount in container.get('volumeMounts', []):
                mount['kdCopyFromImage'] = True

        pa.template = yaml.dump(template, default_flow_style=False)
        pa.save()
        upd.print_log('PA {} patched'.format(pa.name))


# update 00191 stuff bellow

_NGINX_SHARED_ETCD = '/etc/nginx/conf.d/shared-etcd.conf'
_WEBAPP_USER = 'nginx'

_MASTER_ETCD_CONF = '''\
# [member]
ETCD_NAME=default
ETCD_DATA_DIR="/var/lib/etcd/default.etcd"
#ETCD_SNAPSHOT_COUNTER="10000"
#ETCD_HEARTBEAT_INTERVAL="100"
# AC-4634 we have to be sure that etcd will process requests even under heavy
# IO during deploy, so we increase election timeout from default 1000ms to much
# higher value. Max value is 50s https://coreos.com/etcd/docs/latest/tuning.html
# There is no downside for us with big values while etcd cluster consists from
# only one local node. When we want to join more etcd instances we have to set
# correct value AFTER deploy and during new etcd instances provision.
# Also, we set higher disk IO priority to etcd via systemd unit and use
# increased request timeouts for etcdctl with a special wrapper
ETCD_ELECTION_TIMEOUT="20000"
#ETCD_LISTEN_PEER_URLS="http://localhost:2380,http://localhost:7001"
ETCD_LISTEN_CLIENT_URLS="https://0.0.0.0:2379,http://127.0.0.1:4001"
#ETCD_MAX_SNAPSHOTS="5"
#ETCD_MAX_WALS="5"
#ETCD_CORS=""
#
#[cluster]
#ETCD_INITIAL_ADVERTISE_PEER_URLS="http://localhost:2380,http://localhost:7001"
# if you use different ETCD_NAME (e.g. test), set ETCD_INITIAL_CLUSTER value for this name, i.e. "test=http://..."
#ETCD_INITIAL_CLUSTER="default=http://localhost:2380,default=http://localhost:7001"
#ETCD_INITIAL_CLUSTER_STATE="new"
#ETCD_INITIAL_CLUSTER_TOKEN="etcd-cluster"
# Our nginx will proxy 8123 to 127.0.0.1:4001 for authorized hosts
# see "shared-etcd.conf" file
ETCD_ADVERTISE_CLIENT_URLS="https://{0}:2379,http://127.0.0.1:4001"
#ETCD_DISCOVERY=""
#ETCD_DISCOVERY_SRV=""
#ETCD_DISCOVERY_FALLBACK="proxy"
#ETCD_DISCOVERY_PROXY=""
#
#[proxy]
#ETCD_PROXY="off"
#
#[security]
ETCD_CA_FILE="/etc/pki/etcd/ca.crt"
ETCD_CERT_FILE="/etc/pki/etcd/{1}.crt"
ETCD_KEY_FILE="/etc/pki/etcd/{1}.key"
#ETCD_PEER_CA_FILE=""
#ETCD_PEER_CERT_FILE=""
#ETCD_PEER_KEY_FILE=""'''

_K8S_EXTENSIONS = '''\
kind: ThirdPartyResource
apiVersion: extensions/v1beta1
metadata:
  name: network-policy.net.alpha.kubernetes.io
description: "Specification for a network isolation policy"
versions:
- name: v1alpha1'''

_NODE_ETCD_CONF = '''\
# Calico etcd authority
ETCD_AUTHORITY="{0}:2379"
ETCD_SCHEME="https"
ETCD_CA_CERT_FILE="/etc/pki/etcd/ca.crt"
ETCD_CERT_FILE="/etc/pki/etcd/etcd-client.crt"
ETCD_KEY_FILE="/etc/pki/etcd/etcd-client.key"'''

_NODE_CNI_CONF = '''\
{{
    "name": "calico-k8s-network",
    "type": "calico",
    "log_level": "info",
    "ipam": {{
        "type": "calico-ipam"
    }},
    "policy": {{
        "type": "k8s",
        "k8s_api_root": "https://{0}:6443/api/v1/",
        "k8s_auth_token": "{1}"
    }}
}}'''

CALICO_CNI = 'calico-cni-1.3.1-3.el7'
CALICOCTL = 'calicoctl-0.22.0-3.el7'


def _master_etcd_cert(etcd1):
    helpers.local('rm -f /root/.etcd-ca/{0}.host.crt'.format(etcd1))
    helpers.local('rm -f /root/.etcd-ca/{0}.host.csr'.format(etcd1))
    helpers.local('rm -f /root/.etcd-ca/{0}.host.key'.format(etcd1))
    helpers.local(
        'etcd-ca --depot-path /root/.etcd-ca new-cert --ip "{0},127.0.0.1" '
        '--passphrase "" {1}'.format(MASTER_IP, etcd1)
    )
    helpers.local(
        'etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" '
        '{0}'.format(etcd1)
    )
    helpers.local(
        'etcd-ca --depot-path /root/.etcd-ca export {0} --insecure '
        '--passphrase "" | tar -xf -'.format(etcd1)
    )
    helpers.local('mv -f {0}.crt /etc/pki/etcd/'.format(etcd1))
    helpers.local('mv -f {0}.key.insecure /etc/pki/etcd/{0}.key'.format(etcd1))


def _master_etcd_conf(etcd1):
    conf = _MASTER_ETCD_CONF.format(MASTER_IP, etcd1)
    helpers.local('echo "{0}" > /etc/etcd/etcd.conf'.format(conf))


def _master_docker(upd):
    helpers.local('systemctl daemon-reload')
    upd.print_log(helpers.local('systemctl reenable docker'))
    upd.print_log(helpers.restart_service('docker'))
    # Just to be sure and see output in logs:
    upd.print_log(helpers.local('docker info'))


def _master_k8s_node():
    helpers.install_package(CONNTRACK_PACKAGE)
    helpers.local('systemctl reenable kube-proxy')
    helpers.restart_service('kube-proxy')


def _master_calico(upd, calico_network):
    rv = helpers.local(
        'ETCD_AUTHORITY=127.0.0.1:4001 /opt/bin/calicoctl pool add '
        '{} --ipip --nat-outgoing'.format(calico_network)
    )
    if rv.failed:
        raise helpers.UpgradeError(
            "Can't add calicoctl pool: {}".format(rv))

    for i in range(3):
        helpers.local('sync')
        rv = helpers.local('docker pull kuberdock/calico-node:0.22.0-kd2')
        if not rv.failed:
            break
        upd.print_log("Pull calico-node failed. Doing retry {}".format(i))
        sleep(10)
    if rv.failed:
        raise helpers.UpgradeError(
            "Can't pull calico-node image after 3 retries: {}".format(rv))

    helpers.local("sync && sleep 5")
    rv = helpers.local(
        'ETCD_AUTHORITY=127.0.0.1:4001 /opt/bin/calicoctl node '
        '--ip="{0}" --node-image=kuberdock/calico-node:0.22.0-kd2'
        .format(MASTER_IP)
    )
    if rv.failed:
        raise helpers.UpgradeError("Can't start calico node: {}".format(rv))
    helpers.local("sync && sleep 5")


def _master_k8s_extensions():
    helpers.local(
        'sed -i "/^KUBE_API_ARGS/ {s|\\"$| --runtime-config='
        'extensions/v1beta1=true,extensions/v1beta1/thirdpartyresources='
        'true\\"|}" /etc/kubernetes/apiserver'
    )


def _master_network_policy(upd, calico_network):
    RULE_NEXT_TIER = {
        "id": "next-tier",
        "order": 9999,
        "inbound_rules": [{"action": "next-tier"}],
        "outbound_rules": [{"action": "next-tier"}],
        "selector": "all()"
    }
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/failsafe/metadata "
        "'{\"order\": 0}'"
    )
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/kuberdock-hosts/metadata "
        "'{\"order\": 5}'"
    )
    helpers.local(
        'etcdctl mkdir /calico/v1/policy/tier/kuberdock-hosts/policy'
    )
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/kuberdock-hosts/policy/next-tier "
        "'{}'".format(json.dumps(RULE_NEXT_TIER))
    )
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/kuberdock-nodes/metadata "
        "'{\"order\": 10}'"
    )
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/kuberdock-service/metadata "
        "'{\"order\": 20}'"
    )
    helpers.local(
        'etcdctl mkdir /calico/v1/policy/tier/kuberdock-service/policy'
    )
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/kuberdock-service/policy/next-tier "
        "'{}'".format(json.dumps(RULE_NEXT_TIER))
    )

    KD_HOST_ROLE = 'kdnode'
    helpers.local("sync && sleep 5")
    upd.print_log('Trying to get master tunnel IP...')
    retry_pause = 3
    max_retries = 10
    MASTER_TUNNEL_IP = retry(
        get_calico_ip_tunnel_address, retry_pause, max_retries)
    upd.print_log('Master tunnel IP is: {}'.format(MASTER_TUNNEL_IP))
    if not MASTER_TUNNEL_IP:
        raise helpers.UpgradeError("Failed to get master tunnel IP")

    KD_NODES_NEXT_TIER_FOR_PODS = {
        "id": "kd-nodes-dont-drop-pods-traffic",
        "selector": "has(kuberdock-pod-uid)",
        "order": 50,
        "inbound_rules": [{"action": "next-tier"}],
        "outbound_rules": [{"action": "next-tier"}]
    }

    KD_NODES_POLICY = {
        "id": "kd-nodes-public",
        "selector": 'role=="{}"'.format(KD_HOST_ROLE),
        "order": 100,
        "inbound_rules": [
            {
                "src_net": "{}/32".format(MASTER_IP),
                "action": "allow"
            },
            {
                "src_net": "{}/32".format(MASTER_TUNNEL_IP),
                "action": "allow"
            },
            {
                "protocol": "tcp",
                "dst_ports": [22],
                "action": "allow"
            },
        ],
        "outbound_rules": [{"action": "allow"}]
    }
    helpers.local(
        "etcdctl set "
        "/calico/v1/policy/tier/kuberdock-nodes/policy/kuberdock-nodes '{}'"
        .format(json.dumps(KD_NODES_POLICY))
    )
    helpers.local(
        "etcdctl set "
        "/calico/v1/policy/tier/kuberdock-nodes/policy/pods-next-tier '{}'"
        .format(json.dumps(KD_NODES_NEXT_TIER_FOR_PODS))
    )

    KD_MASTER_ROLE = 'kdmaster'
    master_public_tcp_ports = [22, 80, 443, 6443, 2379, 8123, 8118]
    master_public_udp_ports = [123]
    KD_MASTER_POLICY = {
        "id": "kdmaster-public",
        "selector": 'role=="{}"'.format(KD_MASTER_ROLE),
        "order": 200,
        "inbound_rules": [
            {
                "protocol": "tcp",
                "dst_ports": master_public_tcp_ports,
                "action": "allow"
            },
            {
                "protocol": "udp",
                "dst_ports": master_public_udp_ports,
                "action": "allow"
            },
            {
                "action": "next-tier"
            }
        ],
        "outbound_rules": [{"action": "allow"}]
    }
    helpers.local(
        "etcdctl set "
        "/calico/v1/policy/tier/kuberdock-nodes/policy/kuberdock-master '{}'"
        .format(json.dumps(KD_MASTER_POLICY))
    )

    KD_NODES_FAILSAFE_POLICY = {
        "id": "failsafe-all",
        "selector": "all()",
        "order": 100,

        "inbound_rules": [
            {"protocol": "icmp", "action": "allow"},
            {
                "dst_net": calico_network,
                "src_net": "{}/32".format(MASTER_TUNNEL_IP),
                "action": "allow"
            },
            {"action": "next-tier"}
        ],
        "outbound_rules": [
            {
                "protocol": "tcp",
                "dst_ports": [2379],
                "dst_net": "{}/32".format(MASTER_IP),
                "action": "allow"
            },
            {
                "src_net": "{}/32".format(MASTER_TUNNEL_IP),
                "action": "allow"
            },
            {"protocol": "udp", "dst_ports": [67], "action": "allow"},
            {"action": "next-tier"}
        ]
    }
    helpers.local(
        "etcdctl set "
        "/calico/v1/policy/tier/failsafe/policy/failsafe '{}'"
        .format(json.dumps(KD_NODES_FAILSAFE_POLICY))
    )

    MASTER_HOST_ENDPOINT = {
        "expected_ipv4_addrs": [MASTER_IP],
        "labels": {"role": KD_MASTER_ROLE},
        "profile_ids": []
    }
    MASTER_HOSTNAME = socket.gethostname()
    etcd_path = '/calico/v1/host/{0}/endpoint/{0}'.format(MASTER_HOSTNAME)
    helpers.local(
        "etcdctl set {} '{}'".format(
            etcd_path, json.dumps(MASTER_HOST_ENDPOINT))
    )


def _master_dns_policy():
    ki = User.get_internal()
    dns_pod = Pod.query.filter_by(
        name=KUBERDOCK_DNS_POD_NAME, owner=ki).first()
    if dns_pod is not None:
        dns_policy = get_dns_policy_config(ki.id, dns_pod.id)
        Etcd(ETCD_NETWORK_POLICY_SERVICE).put(KUBERDOCK_DNS_POD_NAME,
                                              value=dns_policy)


def _master_pods_policy():
    pods = Pod.query.filter(Pod.status != 'deleted')
    for pod in pods:
        namespace = pod.get_dbconfig()['namespace']
        owner_repr = str(pod.owner.id)
        helpers.local(
            'kubectl annotate ns {0} '
            '"net.alpha.kubernetes.io/network-isolation=yes" '
            '--overwrite=true'.format(namespace)
        )
        helpers.local(
            'kubectl label ns {0} "kuberdock-user-uid={1}" '
            '--overwrite=true'.format(namespace, owner_repr)
        )
        rv = podcollection._get_network_policy_api().post(
            ['networkpolicys'],
            json.dumps(podcollection.allow_same_user_policy(owner_repr)),
            rest=True, ns=namespace)


def _node_kube_proxy():
    run(
        'sed -i "/^KUBE_PROXY_ARGS/ {s|userspace|iptables|}" '
        '/etc/kubernetes/proxy'
    )


RM_FLANNEL_COMMANDS_MASTER = [
    'systemctl disable flanneld',
    'systemctl stop flanneld',
    'rm -f /etc/sysconfig/flanneld',
    'rm -f /etc/systemd/system/flanneld.service',
    'rm -f /etc/systemd/system/docker.service.d/flannel.conf',
    'rm -f /run/flannel/subnet.env',
    'ifdown br0',
    'ip link del br0',
    'rm -f /etc/sysconfig/network-scripts/ifcfg-kuberdock-flannel-br0',
    'ip link del flannel.1',
]

RM_FLANNEL_COMMANDS_NODES = [
    'systemctl disable kuberdock-watcher',
    'systemctl stop kuberdock-watcher',
    'systemctl disable flanneld',
    'systemctl stop flanneld',
    'rm -f /etc/sysconfig/flanneld',
    'rm -f /etc/systemd/system/flanneld.service',
    'rm -f /etc/systemd/system/docker.service.d/flannel.conf',
    'rm -f /run/flannel/subnet.env',
    'ip link del flannel.1',
]


def _master_flannel():
    for cmd in RM_FLANNEL_COMMANDS_MASTER:
        helpers.local(cmd)
    helpers.install_package('flannel', action='remove')
    helpers.local('systemctl daemon-reload')


def _node_flannel():
    for cmd in RM_FLANNEL_COMMANDS_NODES:
        run(cmd)
    # disable kuberdock-watcher but do not remove Kuberdock Network Plugin
    # because it should be replaced by new one
    run('rm -f /etc/systemd/system/kuberdock-watcher.service')
    helpers.remote_install('flannel', action='remove')
    helpers.remote_install('ipset', action='remove')
    run('systemctl daemon-reload')


def _node_calico(upd, with_testing, node_name, node_ip):
    helpers.remote_install(CALICO_CNI, with_testing)
    helpers.remote_install(CALICOCTL, with_testing)

    _create_etcd_config()
    _create_calico_config()

    run('python /var/lib/kuberdock/scripts/kubelet_args.py --network-plugin=')
    run(
        'python /var/lib/kuberdock/scripts/kubelet_args.py '
        '--network-plugin=cni --network-plugin-dir=/etc/cni/net.d'
    )

    # pull image separately to get reed of calicoctl timeouts
    for i in range(3):
        run('sync')
        rv = run('docker pull kuberdock/calico-node:0.22.0-kd2')
        if not rv.failed:
            break
        upd.print_log("Pull calico-node failed. Doing retry {}".format(i))
        sleep(10)
    if rv.failed:
        raise helpers.UpgradeError(
            "Can't pull calico-node image after 3 retries: {}".format(rv))

    rv = run(
        'ETCD_AUTHORITY="{0}:2379" '
        'ETCD_SCHEME=https '
        'ETCD_CA_CERT_FILE=/etc/pki/etcd/ca.crt '
        'ETCD_CERT_FILE=/etc/pki/etcd/etcd-client.crt '
        'ETCD_KEY_FILE=/etc/pki/etcd/etcd-client.key '
        'HOSTNAME="{1}" '
        '/opt/bin/calicoctl node '
        '--ip="{2}" '
        '--node-image=kuberdock/calico-node:0.22.0-kd2'
        .format(MASTER_IP, node_name, node_ip)
    )
    if rv.failed:
        raise helpers.UpgradeError("Can't start calico node: {}".format(rv))


def _create_etcd_config():
    etcd_conf = _NODE_ETCD_CONF.format(MASTER_IP)
    config_file = StringIO()
    get('/etc/kubernetes/config', config_file)
    config = config_file.getvalue()

    if etcd_conf not in config:
        new_fd = StringIO(config + '\n' + etcd_conf)
        put(new_fd, '/etc/kubernetes/config')


def _create_calico_config():
    kube_config = StringIO()
    get('/etc/kubernetes/configfile', kube_config)
    token = yaml.load(kube_config.getvalue())['users'][0]['user']['token']
    run('mkdir -p /etc/cni/net.d')
    cni_conf = _NODE_CNI_CONF.format(MASTER_IP, token)
    run("echo '{0}' > /etc/cni/net.d/10-calico.conf".format(cni_conf))


def _node_policy_agent(hostname):
    ki = User.get_internal()
    token = get_node_token()
    create_policy_pod(hostname, ki, token)


def _master_service_update():
    services = Services()
    all_svc = services.get_all()
    pc = PodCollection()
    for svc in all_svc:
        selector = svc['spec'].get('selector', {})
        labels = svc['metadata'].get('labels', {})
        if KUBERDOCK_POD_UID in selector and KUBERDOCK_TYPE not in labels:
            namespace = svc['metadata']['namespace']
            name = svc['metadata']['name']
            data = {'metadata': {'labels':
                                 {KUBERDOCK_TYPE: LOCAL_SVC_TYPE,
                                  KUBERDOCK_POD_UID: namespace}}}
            rv = services.patch(name, namespace, data)
            raise_if_failure(rv, "Couldn't patch local service: {}".format(rv))
            pod = pc._get_by_id(namespace)
            if pod.status == POD_STATUSES.running:
                run_service(pod)


def _node_move_config():
    config = 'kuberdock.json'
    old_path = os.path.join(
        "/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/", config)
    new_path = os.path.join(NODE_DATA_DIR, config)
    with quiet():
        run("mv {} {}".format(old_path, new_path))
    fd = StringIO()
    get(new_path, fd)
    data = json.loads(fd.getvalue())
    data['network_interface'] = NODE_TOBIND_EXTERNAL_IPS
    new_fd = StringIO()
    json.dump(data, new_fd)
    put(new_fd, new_path)


def _master_firewalld():
    helpers.local('systemctl stop firewalld')
    helpers.local('systemctl disable firewalld')
    helpers.install_package('firewalld', action='remove')
    helpers.local('systemctl daemon-reload')


def _add_nodes_host_endpoints():
    """Adds calico host endpoint for every node,
    sets DefaultEndpointToHostAction to DROP.
    """
    for node in db.session.query(Node).all():
        complete_calico_node_config(node.hostname, node.ip)


def overlaps(net1, net2):
    nets = []
    for net in (net1, net2):
        netstr, bits = net.split('/')
        ipaddr = int(''.join(['%02x' % int(x) for x in netstr.split('.')]), 16)
        first = ipaddr & (0xffffffff ^ (1 << (32 - int(bits)))-1)
        last = ipaddr | (1 << (32 - int(bits)))-1
        nets.append((first, last))
    return ((nets[1][0] <= nets[0][0] <= nets[1][1] or
             nets[1][0] <= nets[0][1] <= nets[1][1]) or
            (nets[0][0] <= nets[1][0] <= nets[0][1] or
             nets[0][0] <= nets[1][1] <= nets[0][1]))


def get_calico_network(host_nets):
    nets = host_nets.splitlines()
    base_net = '10.0.0.0/8'
    filtered = [ip_net for ip_net in nets if overlaps(ip_net, base_net)]
    # just create sequence 127,126,128,125,129,124,130,123,131,122,132...
    addrs = list(chain(*zip(range(127, 254), reversed(range(0, 127)))))
    for addr in addrs:
        net = '10.{}.0.0/16'.format(addr)
        if not any(overlaps(host_net, net) for host_net in filtered):
            return str(net)


def checkout_calico_network():
    cp = ConfigParser.ConfigParser()
    cp.read(KUBERDOCK_MAIN_CONFIG)
    try:
        v = cp.get('main', 'CALICO_NETWORK')
    except ConfigParser.Error:
        v = None
    if v:
        return v
    nets = helpers.local("ip -o -4 addr | grep -vP '\slo\s' | awk '{print $4}'")
    calico_network = get_calico_network(nets)
    if not calico_network:
        raise helpers.UpgradeError("Can't find suitable network for Calico")
    cp.set('main', 'CALICO_NETWORK', calico_network)
    with open(KUBERDOCK_MAIN_CONFIG, 'wb') as configfile:
        cp.write(configfile)
    return calico_network


def upgrade(upd, with_testing, *args, **kwargs):
    _update_nonfloating_config(upd)
    _update_00200_upgrade(upd)  # db migration
    _add_public_access_type(upd)
    calico_network = checkout_calico_network()
    settings.CALICO_NETWORK = calico_network
    _update_00176_upgrade(upd)
    _update_00185_upgrade()
    _update_00186_upgrade()
    _update_00191_upgrade(upd, calico_network)
    _update_00197_upgrade(upd)
    _update_00201_upgrade(upd)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _update_node_nonfloating_config(upd)
    _update_00174_upgrade_node(upd, with_testing)
    _update_00176_upgrade_node(upd, with_testing)
    _update_00179_upgrade_node(env)
    _update_00188_upgrade_node()
    _update_00191_upgrade_node(upd, with_testing, env, **kwargs)
    helpers.reboot_node(upd)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass


def post_upgrade_nodes(upd, with_testing, *args, **kwargs):
    _update_00191_post_upgrade_nodes()
