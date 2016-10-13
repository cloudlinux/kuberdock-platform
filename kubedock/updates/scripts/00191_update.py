import json
from StringIO import StringIO
from fabric.operations import run, get, put
from fabric.context_managers import quiet
from os import path
import socket

from kubedock.kapi.nodes import (
    KUBERDOCK_DNS_POD_NAME,
    create_policy_pod,
    get_dns_policy_config,
    get_node_token,
)
from kubedock.pods.models import Pod
from kubedock.settings import (
    ETCD_NETWORK_POLICY_SERVICE,
    KUBERDOCK_INTERNAL_USER,
    MASTER_IP, NODE_DATA_DIR, NODE_TOBIND_EXTERNAL_IPS
)
from kubedock.updates import helpers
from kubedock.users.models import User
from kubedock.utils import Etcd, get_calico_ip_tunnel_address

from kubedock.kapi.helpers import Services, LOCAL_SVC_TYPE
from kubedock.kapi.helpers import KUBERDOCK_POD_UID, KUBERDOCK_TYPE
from kubedock.kapi.podutils import raise_if_failure
from kubedock.kapi import podcollection
from kubedock.kapi.podcollection import PodCollection, run_service
from kubedock.utils import POD_STATUSES
from kubedock.nodes.models import Node
from kubedock.kapi.node_utils import complete_calico_node_config
from kubedock.core import db

#
# WARNING: etcd should be >= 2.0.10 for successful Calico node running
# WARNING: kubernetes should be >= 1.2.0 for Network policy applying
#

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


def _master_shared_etcd():
    helpers.local(
        'sed "s/@MASTER_IP@/{0}/g" '
        '"/var/opt/kuberdock/conf/shared-etcd.conf.template" > '
        '"{1}"'.format(MASTER_IP, _NGINX_SHARED_ETCD)
    )
    helpers.local('chown "{0}" "{1}"'.format(_WEBAPP_USER, _NGINX_SHARED_ETCD))


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


def _master_docker():
    helpers.local('systemctl reenable docker')
    helpers.restart_service('docker')


def _master_k8s_node():
    helpers.local('systemctl reenable kube-proxy')
    helpers.restart_service('kube-proxy')


def _master_calico():
    helpers.local(
        'curl https://github.com/projectcalico/calico-containers/releases/'
        'download/v0.22.0/calicoctl --create-dirs --location '
        '--output /opt/bin/calicoctl --silent --show-error'
    )
    helpers.local('chmod +x /opt/bin/calicoctl')
    helpers.local(
        'curl https://github.com/projectcalico/k8s-policy/releases/download/'
        'v0.1.4/policy --create-dirs --location --output /opt/bin/policy '
        '--silent --show-error'
    )
    helpers.local('chmod +x /opt/bin/policy')
    helpers.local(
        'ETCD_AUTHORITY=127.0.0.1:4001 /opt/bin/calicoctl pool add '
        '10.1.0.0/16 --ipip --nat-outgoing'
    )
    helpers.local(
        'ETCD_AUTHORITY=127.0.0.1:4001 /opt/bin/calicoctl node '
        '--ip="{0}" --node-image=kuberdock/calico-node:0.22.0.confd'
        .format(MASTER_IP)
    )


def _master_k8s_extensions():
    helpers.local(
        'sed -i "/^KUBE_API_ARGS/ {s|\\"$| --runtime-config='
        'extensions/v1beta1=true,extensions/v1beta1/thirdpartyresources='
        'true\\"|}" /etc/kubernetes/apiserver'
    )


def _master_network_policy():
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
        "'{}'".format(json.dumps(RULE_NEXT_TIER)))
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/kuberdock-hosts/metadata "
        "'{\"order\": 30}'"
    )
    helpers.local(
        'etcdctl mkdir /calico/v1/policy/tier/kuberdock-hosts/policy')
    helpers.local(
        "etcdctl set /calico/v1/policy/tier/kuberdock-hosts/policy/next-tier "
        "'{}'".format(json.dumps(RULE_NEXT_TIER)))

    KD_HOST_ROLE = 'kdnode'
    MASTER_TUNNEL_IP = get_calico_ip_tunnel_address()

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
        ],
        "outbound_rules": [{"action": "allow"}]
    }
    helpers.local(
        "etcdctl set "
        "/calico/v1/policy/tier/kuberdock-nodes/policy/kuberdock-nodes '{}'"
        .format(json.dumps(KD_NODES_POLICY))
    )

    KD_MASTER_ROLE = 'kdmaster'
    master_public_tcp_ports = [80, 443, 6443, 2379, 8123, 8118]
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
                "protocol": "tcp",
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
            {
                "protocol": "tcp",
                "dst_ports": [22],
                "action": "allow"
            },
            {"protocol": "icmp", "action": "allow"},
            {
                "dst_net": "10.1.0.0/16",
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

def _get_internal_user():
    return User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()


def _master_dns_policy():
    ki = _get_internal_user()
    dns_pod = Pod.query.filter_by(
        name=KUBERDOCK_DNS_POD_NAME, owner=ki).first()
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


RM_FLANNEL_COMMANDS = [
    'systemctl stop flanneld',
    'systemctl stop kuberdock-watcher',
    'rm -f /etc/sysconfig/flanneld',
    'rm -f /etc/systemd/system/flanneld.service',
    'rm -f /etc/systemd/system/docker.service.d/flannel.conf',
]


def _master_flannel():
    for cmd in RM_FLANNEL_COMMANDS:
        helpers.local(cmd)
    helpers.local('systemctl daemon-reload')
    helpers.install_package('flannel', action='remove')


def _node_flannel():
    for cmd in RM_FLANNEL_COMMANDS:
        run(cmd)
    # disable kuberdock-watcher but do not remove Kuberdock Network Plugin
    # because it should be replaced by new one
    run('rm -f /etc/systemd/system/kuberdock-watcher.service')
    run('systemctl daemon-reload')
    helpers.remote_install('flannel', action='remove')
    helpers.remote_install('ipset', action='remove')


def _node_calico(node_name, node_ip):
    run(
        'curl https://github.com/projectcalico/calico-cni/releases/download/'
        'v1.3.1/calico --create-dirs --location --output /opt/cni/bin/calico '
        '--silent --show-error'
    )
    run('chmod +x /opt/cni/bin/calico')
    run(
        'curl https://github.com/projectcalico/calico-containers/releases/'
        'download/v0.22.0/calicoctl --create-dirs --location '
        '--output /opt/bin/calicoctl --silent --show-error'
    )
    run('chmod +x /opt/bin/calicoctl')
    etcd_conf = _NODE_ETCD_CONF.format(MASTER_IP)
    run('echo "{0}" >> /etc/kubernetes/config'.format(etcd_conf))
    token = run(
        "grep token /etc/kubernetes/configfile | grep -oP '[a-zA-Z0-9]+$'"
    )
    run('mkdir -p /etc/cni/net.d')
    cni_conf = _NODE_CNI_CONF.format(MASTER_IP, token)
    run("echo '{0}' > /etc/cni/net.d/10-calico.conf".format(cni_conf))
    run('python /var/lib/kuberdock/scripts/kubelet_args.py --network-plugin=')
    run(
        'python /var/lib/kuberdock/scripts/kubelet_args.py '
        '--network-plugin=cni --network-plugin-dir=/etc/cni/net.d'
    )
    with quiet():
        # pull image separately to get reed of calicoctl timeouts
        run('docker pull kuberdock/calico-node:0.22.0.confd')
        run(
            'ETCD_AUTHORITY="{0}:2379" '
            'ETCD_SCHEME=https '
            'ETCD_CA_CERT_FILE=/etc/pki/etcd/ca.crt '
            'ETCD_CERT_FILE=/etc/pki/etcd/etcd-client.crt '
            'ETCD_KEY_FILE=/etc/pki/etcd/etcd-client.key '
            'HOSTNAME="{1}" '
            '/opt/bin/calicoctl node '
            '--ip="{2}" '
            '--node-image=kuberdock/calico-node:0.22.0.confd'
            .format(MASTER_IP, node_name, node_ip)
        )


def _node_policy_agent(hostname):
    ki = _get_internal_user()
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
    old_path = path.join(
        "/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/", config)
    new_path = path.join(NODE_DATA_DIR, config)
    with quiet():
        run("mv {} {}".format(old_path, new_path))
    fd = StringIO()
    get(new_path, fd)
    data = json.loads(fd.getvalue())
    data['network_interface'] = NODE_TOBIND_EXTERNAL_IPS
    new_fd = StringIO()
    json.dump(data, new_fd)
    put(new_fd, new_path)

def _node_k8s(with_testing):
    helpers.remote_install(
        'kubernetes-node-1.2.4-3.el7.cloudlinux', with_testing)

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


def upgrade(upd, with_testing, *args, **kwargs):
    _master_flannel()

    _master_shared_etcd()
    helpers.restart_service('nginx')

    etcd1 = helpers.local('uname -n')
    _master_etcd_cert(etcd1)
    _master_etcd_conf(etcd1)
    helpers.restart_service('etcd')

    _master_docker()
    _master_firewalld()
    _master_k8s_node()
    _master_calico()

    _master_k8s_extensions()
    helpers.restart_master_kubernetes()
    helpers.local('echo "{0}" | kubectl create -f -'.format(_K8S_EXTENSIONS))
    # we need to restart here again, because kubernetes sometimes don't accept
    # extensions onfly
    helpers.restart_master_kubernetes()
    _master_network_policy()

    _master_dns_policy()
    _master_pods_policy()

    _master_service_update()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _node_k8s(with_testing)
    _node_kube_proxy()
    _node_flannel()
    _node_calico(node_name=env.host_string, node_ip=kwargs['node_ip'])
    _node_policy_agent(env.host_string)
    _node_move_config()
    helpers.reboot_node(upd)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass


def post_upgrade_nodes(upd, with_testing, *args, **kwargs):
    _add_nodes_host_endpoints()
