"""
There should be all network policies to help in understanding about
what rules and in what order is applied to traffic.

Some rules/tiers are created in deploy.sh
"""

from ..utils import get_calico_ip_tunnel_address, find_calico_host_by_ip
from ..exceptions import SubsystemtIsNotReadyError
from .. import settings
from ..settings import (
    ELASTICSEARCH_REST_PORT,
    ELASTICSEARCH_PUBLISH_PORT,
    MASTER_IP, KD_NODE_HOST_ENDPOINT_ROLE
)

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


def get_rhost_policy(ip):
    """
    Allow all traffic from this ip to pods. Needed cPanel like hosts.
    This Rule is in "kuberdock-hosts" tier
    :param ip:
    :return:
    """
    return {
        "id": ip,
        "order": 10,
        "inbound_rules": [
            {
                "action": "allow",
                "src_net": "{0}/32".format(ip)
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
        "selector": "role==\"kdnode\"",
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
