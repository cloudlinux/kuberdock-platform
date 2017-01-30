
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

"""
There should be all network policies to help in understanding about
what rules and in what order is applied to traffic.

Some rules/tiers are created in deploy.sh
"""

from ..utils import get_calico_ip_tunnel_address
from ..exceptions import RegisteredHostError, SubsystemtIsNotReadyError
from .. import settings
from ..settings import (
    CALICO_NETWORK,
    ELASTICSEARCH_REST_PORT,
    ELASTICSEARCH_PUBLISH_PORT,
    MASTER_IP, KD_MASTER_HOST_ENDPOINT_ROLE, KD_NODE_HOST_ENDPOINT_ROLE,
)

# Node host isolation
# 22 - ssh
NODE_PUBLIC_TCP_PORTS = [22]

# Master host isolation
# 22 - ssh
# 80, 443 - KD API & web server
# 6443 - kube-api server secure
# 2379 - etcd secure
# 8123, 8118 open ports for cpanel calico and kube-proxy
MASTER_PUBLIC_TCP_PORTS = [22, 80, 443, 6443, 2379, 8123, 8118]
# 123 - ntp
MASTER_PUBLIC_UDP_PORTS = [123]

PUBLIC_PORT_POLICY_NAME = 'public'


# Main ns policy
def allow_same_user_policy(owner_repr):
    """
    This policy will allow pods to communicate only with pods of the same user
    :param owner_repr: str(user.id)
    """
    return {
        "kind": "NetworkPolicy",
        "apiVersion": settings.KUBE_NP_API_VERSION,
        "metadata": {
            "name": owner_repr
        },
        "spec": {
            "podSelector": {
                "kuberdock-user-uid": owner_repr
            },
            "ingress": [{
                "from": [{
                    "namespaces": {"kuberdock-user-uid": owner_repr}
                }]
            }]
        }
    }


def get_dns_policy_config(user_id, namespace):
    """
    This policy will allow any pod to use our dns internal pod.
    :param user_id: user.id of Kuberdock-internal user
    :param namespace: NS of this dns pod
    """
    return {
        "id": "kuberdock-dns",
        "order": 10,
        "inbound_rules": [{
            "action": "allow"
        }],
        "outbound_rules": [{
            "action": "allow"
        }],
        "selector": ("kuberdock-user-uid == '{0}' && calico/k8s_ns == '{1}'"
                     .format(user_id, namespace))
    }


def get_logs_policy_config(user_id, namespace, logs_pod_name):
    calico_ip_tunnel_address = get_calico_ip_tunnel_address()
    if not calico_ip_tunnel_address:
        raise SubsystemtIsNotReadyError(
            'Can not get calico IPIP tunnel address')
    return {
        "id": logs_pod_name + '-master-access',
        "order": 10,
        "inbound_rules": [
            # First two rules are for access to elasticsearch from master
            # Actually works the second rule (with master ip tunnel address)
            {
                "protocol": "tcp",
                "dst_ports": [ELASTICSEARCH_REST_PORT],
                "src_net": MASTER_IP + '/32',
                "action": "allow",
            },
            {
                "protocol": "tcp",
                "dst_ports": [ELASTICSEARCH_REST_PORT],
                "src_net": u'{}/32'.format(calico_ip_tunnel_address),
                "action": "allow",
            },
            # This rule should allow interaction of different elasticsearch
            # pods. It must work without this rule (by k8s policies), but it
            # looks like this policy overlaps k8s policies.
            # So just allow access to elasticsearch from service pods.
            # TODO: looks like workaround, may be there is a better solution.
            {
                'protocol': 'tcp',
                'dst_ports': [
                    ELASTICSEARCH_REST_PORT, ELASTICSEARCH_PUBLISH_PORT
                ],
                "src_selector": "kuberdock-user-uid == '{}'".format(user_id),
                'action': 'allow',
            },
        ],
        "outbound_rules": [{
            "action": "allow"
        }],
        "selector": ("kuberdock-user-uid == '{0}' && calico/k8s_ns == '{1}'"
                     .format(user_id, namespace))
    }


def get_rhost_policy(host_ip, tunl_ip):
    """
    Allow all traffic from this ip to pods. Needed cPanel like hosts.
    This Rule is in "kuberdock-hosts" tier
    :param host_ip: Remote Host IP Address
    :param tunl_ip: Remote Host Tunnel IP Address
    :return:
    """
    if not (host_ip and tunl_ip):
        raise RegisteredHostError(
            details={'message': 'Invalid data received during registration: '
                     'Host IP - {0}, Tunnel IP - {1}'.format(host_ip, tunl_ip)
            }
        )

    return {
        "id": host_ip,
        "order": 10,
        "inbound_rules": [
            {
                "action": "allow",
                "src_net": "{0}/32".format(host_ip)
            },
            {
                # Tested that we need this rule too
                "action": "allow",
                "src_net": "{0}/32".format(tunl_ip)
            },
            # {"action": "next-tier"} # TODO like for generic KD nodes?
        ],
        "outbound_rules": [{
            "action": "next-tier"
        }],
        "selector": "all()"
    }


def allow_public_ports_policy(ports, owner):
    """
    This policy allow traffic for public ports of the pod from anywhere.
    This traffic is allowed for ALL pod's IPs including internal.
    :param ports: dict of pod's ports sepc
    :param owner: str(user.id)
    """
    owner_repr = str(owner.id)
    ingress_ports = []
    for port in ports:
        public_port = {'port': port['port'], 'protocol': port['protocol']}
        origin_port = {'port': port['targetPort'], 'protocol': port['protocol']}
        ingress_ports.append(public_port)
        # TODO we can try to limit access even more if we set rule that
        # origin_ports are accessible only from node ip (kube-proxy) but this
        # is tricky and require low-level policy. Also this has little to none
        # benefit for us because this port is public anyway. We should revice
        # it later and take into account AWS case.
        ingress_ports.append(origin_port)
    return {
        "kind": "NetworkPolicy",
        "metadata": {
            "name": PUBLIC_PORT_POLICY_NAME
        },
        "spec": {
            # TODO do we really need this selector here?
            "podSelector": {
                "kuberdock-user-uid": owner_repr
            },
            "ingress": [{
                "ports": ingress_ports
            }]
        }
    }


def get_node_host_endpoint_policy(node_hostname, node_ip):
    """Returns polices for a node's host endpoint.
    Allows all traffic from this node_ip. Forbids all traffic from pods to
    node ip.
    """
    # This deny rule will work only for one node, so all such policies
    # for nodes must be checked. Also there must be next policy (next by
    # order) to jump to next-tier for selector 'has(kuberdock-pod-uid)'.
    # Without this rule traffic will be dropped by default in this tier.
    pods_forbid_policy = {
        "id": "isolate-from-pods-" + node_hostname,
        "selector": 'has(kuberdock-pod-uid)',
        "order": 10,
        "inbound_rules": [
        ],
        "outbound_rules": [
            {
                "dst_net": "{}/32".format(node_ip),
                "action": "deny"
            }
        ]
    }
    node_allow_policy = {
        "id": "kd-nodes-" + node_hostname,
        "selector": 'role=="{}"'.format(KD_NODE_HOST_ENDPOINT_ROLE),
        "order": 110,
        "inbound_rules": [
            {
                "src_net": "{}/32".format(node_ip),
                "action": "allow"
            },
        ],
        "outbound_rules": []
    }
    return [pods_forbid_policy, node_allow_policy]


def get_node_allowed_ports_policy(rules):
    return {
        "id": "kd-nodes-allowed-ports",
        "order": 105,
        "selector": "role==\"{0}\"".format(KD_NODE_HOST_ENDPOINT_ROLE),
        "inbound_rules": rules,
        "outbound_rules": [
            {
                "action": "allow",
            }
        ],
    }


def get_node_allowed_ports_rule(ports, protocol):
    return {
        "action": "allow",
        "dst_ports": ports,
        "protocol": protocol,
    }


def get_pod_restricted_ports_policy(rules):
    return {
        "id": "kd-restricted-ports",
        "inbound_rules": [],
        "order": 5,
        "outbound_rules": rules,
        "selector": "has(kuberdock-pod-uid)"
    }


def get_pod_restricted_ports_rule(ports, protocol):
    return {
        "!dst_net": CALICO_NETWORK,
        "action": "deny",
        "dst_ports": ports,
        "protocol": protocol
    }


# This rule is needed for remote hosts tier (kuberdock-hosts). It will allow
# next tiers processing if some rhosts policy is in this tier.
# Remote hosts policies use selector 'all()'.
RULE_NEXT_TIER = {
    "id": "next-tier",
    "order": 9999,
    "inbound_rules": [{"action": "next-tier"}],
    "outbound_rules": [{"action": "next-tier"}],
    "selector": "all()"
}


# This next tier policy is needed for traffic that will come from pods
# and is not match any deny rules. Those deny rule will be created for each
# node when node is added.
KD_NODES_NEXT_TIER_FOR_PODS = {
    "id": "kd-nodes-dont-drop-pods-traffic",
    "selector": "has(kuberdock-pod-uid)",
    "order": 50,
    "inbound_rules": [{"action": "next-tier"}],
    "outbound_rules": [{"action": "next-tier"}]
}


def get_tiers():
    return {
        'failsafe': {
            'order': 0,
            'policies': {
                'failsafe': get_nodes_failsafe_policy()
            }
        },
        'kuberdock-hosts': {
            'order': 5,
            'policies': {
                'next-tier': RULE_NEXT_TIER,
            },
        },
        'kuberdock-nodes': {
            'order': 10,
            'policies': {
                'kuberdock-master': get_master_policy(),
                'kuberdock-nodes': get_nodes_policy(),
                'pods-next-tier': KD_NODES_NEXT_TIER_FOR_PODS,
            },
        },
        'kuberdock-service': {
            'order': 20,
            'policies': {
                'next-tier': RULE_NEXT_TIER,
            },
        },
    }


# We will add endpoints for all nodes ('host endpoints', see
# http://docs.projectcalico.org/en/latest/etcd-data-model.html#endpoint-data).
# This will close all traffic to and from nodes, so we should explicitly allow
# what we need. Also we create failsafe rules as recommended in
# http://docs.projectcalico.org/en/latest/bare-metal.html#failsafe-rules
def get_nodes_policy():
    calico_ip_tunnel_address = get_calico_ip_tunnel_address()
    if not calico_ip_tunnel_address:
        raise SubsystemtIsNotReadyError(
            'Can not get calico IPIP tunnel address')
    return {
        "id": "kd-nodes-public",
        "selector": "role==\"{0}\"".format(KD_NODE_HOST_ENDPOINT_ROLE),
        "order": 100,
        "inbound_rules": [
            {
                "src_net": "{0}/32".format(MASTER_IP),
                "action": "allow"
            },
            {
                "src_net": "{0}/32".format(calico_ip_tunnel_address),
                "action": "allow"
            },
            {
                "protocol": "tcp",
                "dst_ports": NODE_PUBLIC_TCP_PORTS,
                "action": "allow"
            }
        ],
        "outbound_rules": [{"action": "allow"}]
    }


def get_master_policy():
    return {
        "id": "kdmaster-public",
        "selector": "role==\"{0}\"".format(KD_MASTER_HOST_ENDPOINT_ROLE),
        "order": 200,
        "inbound_rules": [
            {
                "protocol": "tcp",
                "dst_ports": MASTER_PUBLIC_TCP_PORTS,
                "action": "allow"
            },
            {
                "protocol": "udp",
                "dst_ports": MASTER_PUBLIC_UDP_PORTS,
                "action": "allow"
            },
            {
                "action": "next-tier"
            }
        ],
        "outbound_rules": [{"action": "allow"}]
    }


# Here we allow all traffic from master to calico subnet. It is a
# workaround and it must be rewritten to specify more secure policy
# for access from master to some services.
def get_nodes_failsafe_policy():
    calico_ip_tunnel_address = get_calico_ip_tunnel_address()
    if not calico_ip_tunnel_address:
        raise SubsystemtIsNotReadyError(
            'Can not get calico IPIP tunnel address')
    return {
        "id": "failsafe-all",
        "selector": "all()",
        "order": 100,
        "inbound_rules": [
            {"protocol": "icmp", "action": "allow"},
            {
                "dst_net": CALICO_NETWORK,
                "src_net": "{0}/32".format(calico_ip_tunnel_address),
                "action": "allow"
            },
            {"action": "next-tier"}
        ],
        "outbound_rules": [
            {
                "protocol": "tcp",
                "dst_ports": [2379],
                "dst_net": "{0}/32".format(MASTER_IP),
                "action": "allow"
            },
            {
                "src_net": "{0}/32".format(calico_ip_tunnel_address),
                "action": "allow"
            },
            {"protocol": "udp", "dst_ports": [67], "action": "allow"},
            {"action": "next-tier"}
        ]
    }


# master calico host endpoint
def get_master_host_endpoint():
    return {
        "expected_ipv4_addrs": [MASTER_IP],
        "labels": {"role": KD_MASTER_HOST_ENDPOINT_ROLE},
        "profile_ids": []
    }
