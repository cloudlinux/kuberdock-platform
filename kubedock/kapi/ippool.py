
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

import operator
import json

import ipaddress
from flask import current_app
from ..kapi.helpers import KubeQuery
from ..kapi import podutils

from .podcollection import PodCollection
from .. import utils
from .. import validation
from ..exceptions import APIError, NoFreeIPs, CanNotRemoveIPPool
from ..kapi.node import Node as K8SNode, NodeException, NodeNotFound
from ..kapi.lbpoll import LoadBalanceService, get_service_provider
from ..nodes.models import Node
from ..domains.models import BaseDomain
from ..pods.models import IPPool, PodIP, ip_network, Pod
from ..users.models import User
from ..settings import AWS, KUBERDOCK_INTERNAL_USER
from ..constants import KUBERDOCK_INGRESS_POD_NAME


class IpAddrPool(object):
    @staticmethod
    def get(net=None, page=None):
        """Returns list of networks or a single network.
        :param net: network ('x.x.x.x/x') optional. If it is not specified,
        then will be returned list of all networks. If it specified, then will
        be returned single network or None
        :param page: optional page to restrict list of hosts in each selected
            network
        """
        if AWS:
            all_pods = Pod.query.filter(Pod.status != 'deleted').all()
            pods_data = [(i.id, i.name, i.owner.username) for i in all_pods
                         if i.owner.username != KUBERDOCK_INTERNAL_USER]
            lbs = LoadBalanceService()
            names = lbs.get_dns_by_pods([i[0] for i in pods_data])
            allocation = [(names[i[0]], i[1], 'busy', i[2]) for i in pods_data
                          if i[0] in names]
            return {'allocation': allocation,
                    'free_hosts': [],
                    'blocked_list': [],
                    'id': None,
                    'network': None,
                    'page': page or 1,
                    'pages': 1,
                    'ipv6': False,
                    'node': None}
        if net is None:
            return [p.to_dict(page=page) for p in IPPool.all()]
        rv = IPPool.filter_by(network=net).first()
        if rv is not None:
            return rv.to_dict(page=page)

    @staticmethod
    def get_free():
        """Returns first free ip address from pool of defined networks."""
        try:
            return IPPool.get_free_host()
        except NoFreeIPs:
            return None

    @classmethod
    def create(cls, data):
        # type: (dict) -> dict
        """Creates network instance in db pool of networks.
        :param data: dict with fields 'network' ('x.x.x.x/x'), and optional
            'autoblock' - string of comma separated IPs or IP ranges,
            which define a list of IP addresses to exclude. IP range has a
            following format 10.0.0.1-10.0.0.32. You can mix ranges with
            single IPs, like 10.0.0.1,10.0.0.30-10.0.1.32,10.0.0.2
        :return: pool

        """
        data = validation.V()._api_validation(data or {},
                                              validation.ippool_schema)

        cls._check_if_network_exists(data['network'])

        node_name = data.get('node')
        node = Node.query.filter_by(hostname=node_name).first()
        if node_name is not None:
            if node is None:
                raise APIError('Node does not exist ({})'.format(node_name))

        with utils.atomic():
            pool = IPPool.create(network=data['network'], node=node)
            auto_block = data.get('autoblock')

            # Strip out any spaces between symbols
            if auto_block:
                auto_block = auto_block.replace(' ', '')

            block_list = cls.parse_autoblock(auto_block) if auto_block else []
            pool.block_ip(block_list)

            if node_name and current_app.config['FIXED_IP_POOLS']:
                try:
                    node = K8SNode(hostname=node_name)
                    node.increment_free_public_ip_count(len(pool.free_hosts()))
                except NodeNotFound:
                    raise APIError(
                        'Node isn\'t deployed yet. Please try later.')

        pool.save()
        return pool

    @classmethod
    @utils.atomic(nested=False)
    def update(cls, network, params):
        net = cls._get_network_by_cidr(network)
        if not params:
            return net

        block_ip = params.get('block_ip')
        unblock_ip = params.get('unblock_ip')
        unbind_ip = params.get('unbind_ip')
        node_name = params.get('node')

        if block_ip and net.block_ip(block_ip) == 0:
            raise APIError("IP is already blocked")

        if unblock_ip and net.unblock_ip(unblock_ip) == 0:
            raise APIError("IP is already unblocked")

        if unbind_ip:
            PodCollection._remove_public_ip(ip=unbind_ip)

        if node_name and current_app.config['FIXED_IP_POOLS']:
            net.node = cls._get_node_by_name(net, node_name)
            cls._update_free_public_ip_counter(net.node.hostname, block_ip,
                                               unblock_ip,
                                               unbind_ip)
        return net

    @staticmethod
    def _update_free_public_ip_counter(hostname, block_ip, unblock_ip,
                                       unbind_ip):
        delta, k8s_node = 0, K8SNode(hostname=hostname)

        if block_ip:
            delta -= 1

        if unblock_ip:
            delta += 1

        if unbind_ip:
            delta += 1

        try:
            k8s_node.increment_free_public_ip_count(delta)
        except NodeException:
            raise APIError('Could not modify IP. Please try later')

    @staticmethod
    def _get_node_by_name(net, node_name):
        if PodIP.filter_by(network=net.network).first() is not None:
            raise APIError(
                "You cannot change the node of network '{0}' while "
                "some of IP-addresses of this network were assigned to "
                "Pods".format(net.network)
            )
        node = Node.query.filter_by(hostname=node_name).first()
        if node is None:
            raise APIError('Node is not exists ({0})'.format(node_name))
        return node

    @staticmethod
    def _check_if_network_exists(network):
        net = ipaddress.IPv4Network(network)
        for pool in IPPool.all():
            if pool.network == net:
                raise APIError('Network {} already exists'.format(network))
            if net.overlaps(ipaddress.IPv4Network(pool.network)):
                raise APIError(
                    'New {} network overlaps {} which already exists'.format(
                        network, pool.network))

    @staticmethod
    def get_user_addresses(user):
        pods = {pod.id: pod.name
                for pod in user.pods if pod.status != 'deleted'}

        # AWS requires different processing because of ELB instead of IPs
        if AWS:
            elb_dict = LoadBalanceService().get_dns_by_user(user.id)
            return [dict(id=v, pod=pods.get(k), pod_id=k)
                    for k, v in elb_dict.items()]

        return [{'id': str(ipaddress.ip_address(i.ip_address)),
                 'pod': pods[i.pod_id],
                 'pod_id': i.pod_id}
                for i in PodIP.filter(PodIP.pod_id.in_(pods.keys()))]

    @classmethod
    def delete(cls, network):
        network = str(ip_network(network))
        pool = IPPool.filter_by(network=network).first()
        if not pool:
            raise APIError("Network '{0}' does not exist".format(network), 404)
        cls._check_if_network_used_by_pod(network)
        cls._remove_ingress_pod_if_possible_and_needed(network)
        cls._delete_network(network, pool)

    @staticmethod
    def _remove_ingress_pod_if_possible_and_needed(network):
        pod = Pod.query.\
            filter(Pod.name == KUBERDOCK_INGRESS_POD_NAME).join(PodIP).\
            filter(PodIP.network == network).first()

        if pod is None:
            return

        if BaseDomain.query.count() > 0:
            raise CanNotRemoveIPPool(
                "Can not remove network because there is an Ingress "
                "controller pod running on it. Please remove all "
                "domains from KuberDock so it would be possible to "
                "remove the controller and the network")

        PodCollection().delete(pod.id, force=True)

    @staticmethod
    def _delete_network(network, pool):
        free_ip_count = len(pool.free_hosts())
        IPPool.query.filter_by(network=network).delete()

        if pool.node and current_app.config['FIXED_IP_POOLS']:
            try:
                node = K8SNode(hostname=pool.node.hostname)
                node.increment_free_public_ip_count(-free_ip_count)
            except NodeNotFound:
                # If node is missing in kubernetes it is safe to fail silently
                # because ip counters are missing too
                pass

    @staticmethod
    def _check_if_network_used_by_pod(network):
        """
        Does not take into account the ingress pod as it should go away if
        not needed anymore so the network could be removed
        """
        pod_ip = PodIP.filter(PodIP.network == network).\
            join(PodIP.pod).\
            filter(Pod.name != KUBERDOCK_INGRESS_POD_NAME).first()

        if pod_ip is not None:
            raise APIError("You cannot delete this network '{0}' while "
                           "some of IP-addresses of this network are "
                           "assigned to Pods".format(network))

    @staticmethod
    def _get_network_by_cidr(network):
        net = IPPool.filter_by(network=network).first()
        if net is None:
            raise APIError("Network '{0}' does not exist".format(network), 404)
        return net

    @staticmethod
    def parse_autoblock(data):
        # type: (str) -> set
        def _parse(item):
            # Try to parse item as a single IP
            try:
                ipaddress.IPv4Address(item)
                return {item}
            except ipaddress.AddressValueError:
                pass

            # Try parse item as ip range: ip1-ip2
            try:
                first_ip, last_ip = [utils.ip2int(i) for i in item.split('-')]
                return {utils.int2ip(n) for n in range(first_ip, last_ip + 1)}
            except ValueError:
                raise APIError(
                    'Exclude IP\'s are expected to be in the form of '
                    '10.0.0.1,10.0.0.4 or 10.1.0.10-10.1.1.54 or both '
                    'comma-separated')

        ip_sets = (_parse(unicode(d)) for d in data.split(','))
        return reduce(operator.or_, ip_sets)

    @staticmethod
    def assign_ip_to_pod(pod_id, node_hostname=None):
        """
        Picks free pubic IP and assigns it to the specified pod
        :param pod_id: id of the pod IP should be assigned to
        :param node_hostname: optional node hostname. If specified only IP's
        from this node will be used
        :return: string representation of the picked IP
        """
        pc = PodCollection()
        assigned_ip = pc.assign_public_ip(pod_id, node=node_hostname)
        kq = KubeQuery()
        pods = kq.get(['pods'],
                      {'labelSelector':
                       'kuberdock-pod-uid={}'.format(pod_id)})
        for p in pods.get('items', tuple()):
            namespace = p['metadata']['namespace']
            name = p['metadata']['name']
            data = json.dumps({'metadata':
                               {'labels':
                                {'kuberdock-public-ip': assigned_ip}}})
            rv = kq.patch(['pods', name], data=data, ns=namespace)
            podutils.raise_if_failure(rv, 'Error while try to patch')
        svc = get_service_provider()
        services = svc.get_by_pods(pod_id)
        if services.get(pod_id, None):
            svc.update_publicIP(services[pod_id], assigned_ip)
        pc.update(pod_id,
                  {'command': 'change_config',
                   'node': node_hostname,
                   'public_ip': assigned_ip})
        return assigned_ip

    @staticmethod
    def get_mode():
        if AWS:
            return 'aws'
        if current_app.config['FIXED_IP_POOLS']:
            return 'fixed'
        return 'floating'

    @staticmethod
    def get_networks_list():
        """Returns list of networks.
        :return: list of networks with available ips count
        """
        if AWS:
            return [{
                'id': None,
                'network': None,
                'ipv6': False,
                'node': None,
                'free_host_count': 0,
            }]
        return [p.main_info_dict() for p in IPPool.all()]

    @staticmethod
    def ip_list_by_blocks(ip_list):
        if not ip_list:
            return []
        ip_list = sorted(ip_list)
        start_end_ip = [ip_list[0]]
        for num in xrange(1, len(ip_list)):
            ip = ip_list[num]
            prev_in_list = ip_list[num - 1]
            prev_ip = ip - 1
            if prev_ip != prev_in_list:
                start_end_ip.append(prev_in_list)
                start_end_ip.append(ip)
        start_end_ip.append(ip_list[-1])
        return zip(*[iter(start_end_ip)] * 2)

    @staticmethod
    def get_missed_intervals(ip_blocks, start_ip, end_ip):
        missed_blocks = []
        next_ip = int(start_ip)
        for block in ip_blocks:
            if block[0] > next_ip:
                missed_blocks.append((next_ip, block[0] - 1))
            next_ip = block[1] + 1
        if int(end_ip) >= next_ip:
            missed_blocks.append((next_ip, int(end_ip)))
        return missed_blocks

    @classmethod
    def get_network_ips(cls, net):
        """Return list of subnets
        :param net: network ('x.x.x.x/x') or anything for AWS
        """
        if AWS:
            pods_data = list(
                Pod.query.filter(Pod.status != 'deleted').join(User).
                values(Pod.id, Pod.name, User.username))

            lbs = LoadBalanceService()
            names = lbs.get_dns_by_pods([i[0] for i in pods_data])

            blocks = [(names[id_], names[id_], 'busy', name, username)
                      for id_, name, username in pods_data if id_ in names]

            return {
                'id': 'aws',
                'network': None,
                'ipv6': False,
                'node': None,
                'free_host_count': 0,
                'blocks': blocks,
            }

        ipPool = IPPool.filter_by(network=net).first()
        if ipPool is not None:
            info = ipPool.main_info_dict()
            blocks = []

            blocked_ips = ipPool.get_blocked_set(as_int=True)

            allocated_ips = {pod.ip_address: pod.get_pod()
                             for pod in PodIP.filter_by(network=net)}
            for ip_address, pod in allocated_ips.iteritems():
                state = 'busy'
                if ip_address in blocked_ips:
                    state = 'blocked'
                    blocked_ips.discard(ip_address)
                blocks.append((ip_address, ip_address, state, pod))

            busy_ips = allocated_ips.keys()
            network = ip_network(net)

            blocked_blocks = cls.ip_list_by_blocks(sorted(blocked_ips))
            busy_blocks = cls.ip_list_by_blocks(sorted(busy_ips))
            non_free_blocks = sorted(set(blocked_blocks) | set(busy_blocks))
            free_blocks = cls.get_missed_intervals(non_free_blocks,
                                                   network.network_address,
                                                   network.broadcast_address)

            # merge blocks
            for item in blocked_blocks:
                blocks.append(item + ('blocked',))
            for item in free_blocks:
                blocks.append(item + ('free',))
            sorted_blocks = sorted(blocks)

            info.update({
                'blocks': sorted_blocks,
            })
            return info
