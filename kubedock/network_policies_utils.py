
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

import json

import etcd

from .allowed_ports.models import AllowedPort
from .kapi import allowed_ports, restricted_ports
from .kapi.network_policies import (
    get_dns_policy_config,
    get_logs_policy_config,
    get_master_host_endpoint,
    get_rhost_policy,
    get_tiers,
)
from .kapi.node_utils import complete_calico_node_config
from .kapi.service_pods import (
    KUBERDOCK_DNS_POD_NAME,
    get_kuberdock_logs_pod_name,
)
from .nodes.models import Node, RegisteredHost
from .pods.models import Pod
from .restricted_ports.models import RestrictedPort
from .settings import (
    ETCD_CALICO_POLICY_PATH,
    ETCD_CALICO_V_PATH,
    ETCD_NETWORK_POLICY_HOSTS_KEY,
    ETCD_NETWORK_POLICY_SERVICE_KEY,
    ETCD_HOST,
    ETCD_PORT,
)
from .users.models import User
from .utils import get_hostname


def create_network_policies():
    client = etcd.Client(host=ETCD_HOST, port=ETCD_PORT)

    # master endpoint
    master_hostname = get_hostname()
    master_endpoint_key = '/'.join([ETCD_CALICO_V_PATH,
                                    'host', master_hostname,
                                    'endpoint', master_hostname])
    master_endpoint = get_master_host_endpoint()
    client.write(master_endpoint_key, json.dumps(master_endpoint))

    # populate policies
    for tier_name, tier in get_tiers().items():
        tier_key = '/'.join([ETCD_CALICO_POLICY_PATH, tier_name])
        tier_metadata = '/'.join([tier_key, 'metadata'])
        tier_policy = '/'.join([tier_key, 'policy'])

        try:
            client.delete(tier_key, recursive=True)
        except etcd.EtcdKeyNotFound:
            pass

        client.write(tier_metadata, json.dumps({'order': tier['order']}))

        for policy_name, policy in tier.get('policies', {}).items():
            policy_key = '/'.join([tier_policy, policy_name])
            client.write(policy_key, json.dumps(policy))

    # nodes policies
    for node in Node.query:
        complete_calico_node_config(node.hostname, node.ip)

    # rhosts policies
    for rhost in RegisteredHost.query:
        rhost_policy_key = '/'.join([ETCD_NETWORK_POLICY_HOSTS_KEY,
                                     rhost.host])
        rhost_policy = get_rhost_policy(rhost.host, rhost.tunnel_ip)
        client.write(rhost_policy_key, json.dumps(rhost_policy))

    # allowed ports policy
    if AllowedPort.query.first():
        allowed_ports._set_allowed_ports_etcd()

    # restricted ports policy
    if RestrictedPort.query.first():
        restricted_ports._set_restricted_ports_etcd()

    # service pods policies
    owner = User.get_internal()

    # dns pod policy
    dns_pod = Pod.query.filter_by(name=KUBERDOCK_DNS_POD_NAME,
                                  owner=owner).first()
    if dns_pod:
        dns_policy_key = '/'.join([ETCD_NETWORK_POLICY_SERVICE_KEY,
                                   KUBERDOCK_DNS_POD_NAME])
        dns_policy = get_dns_policy_config(owner.id, dns_pod.id)
        client.write(dns_policy_key, json.dumps(dns_policy))

    # logs pods policies
    for node in Node.query:
        pod_name = get_kuberdock_logs_pod_name(node.hostname)
        pod = Pod.query.filter_by(name=pod_name, owner=owner).first()
        if pod:
            logs_policy_key = '/'.join([ETCD_NETWORK_POLICY_SERVICE_KEY,
                                        pod_name])
            logs_policy = get_logs_policy_config(owner.id, pod.id, pod_name)
            client.write(logs_policy_key, json.dumps(logs_policy))
