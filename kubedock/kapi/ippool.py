from itertools import imap

import ipaddress

from .podcollection import PodCollection
from ..pods.models import IPPool, PodIP, ip_network
from ..utils import APIError, atomic


class IpAddrPool(object):

    def get(self, net=None, page=None):
        """Returns list of networks or a single network.
        :param net: network ('x.x.x.x/x') optional. If it is not specified, then
            will be returned list of all networks. If it specified, then will
            be returned single network or None
        :param page: optional page to restrict list of hosts in each selected
            network
        """
        if net is None:
            return [p.to_dict(page=page) for p in IPPool.all()]
        rv = IPPool.filter_by(network=net).first()
        if rv is not None:
            return rv.to_dict(page=page)

    def get_free(self):
        """Returns first free ip address from pool of defined networks."""
        return IPPool.get_free_host()

    def create(self, data):
        """Creates network instance in db pool of networks.
        :param data: dict with fields 'network' ('x.x.x.x/x'), and optional
            'autoblock' - string of comma separated integers, which define
            lowest octet of an ip address in the network. For example 1,4-6
            will exclude 192.168.1.1, 192.168.1.4, 192.168.1.5, 192.168.1.6
            addresses from 192.168.1.0/24 network.
            It's a design feature, for example for subnet
            '192.168.0.0/23' exclusion '1' will exclude two addresses -
            '192.168.0.1', '192.168.1.1'. It seems like non-obvious and
            unexpected behavior.
            TODO: at least redesign ip excluding.
        :return: dict with fields 'network' and 'autoblock'

        """
        try:
            network = ip_network(data.get('network'))
            if IPPool.filter_by(network=str(network)).first():
                raise APIError(
                    'Network {0} already exists'.format(str(network)))
            autoblock = self._parse_autoblock(data.get('autoblock'))
            pool = IPPool(network=str(network))
            block_list = [
                int(ipaddress.ip_address(i))
                for i in imap(unicode, network.hosts())
                if int(i.split('.')[-1]) in autoblock
            ]

            pool.block_ip(block_list)
            pool.save()
            return {'id': str(network),
                    'network': str(network),
                    'autoblock': block_list,
                    'allocation': pool.free_hosts_and_busy(page=1)}
        except (ValueError, AttributeError) as e:
            raise APIError(str(e))

    @atomic(nested=False)
    def update(self, network, params):
        net = IPPool.filter_by(network=network).first()
        if net is None:
            raise APIError("Network '{0}' does not exist".format(network), 404)
        if not params:
            return net.to_dict()
        block_ip = params.get('block_ip')
        if block_ip:
            net.block_ip(block_ip)
        unblock_ip = params.get('unblock_ip')
        if unblock_ip:
            net.unblock_ip(unblock_ip)
        unbind_ip = params.get('unbind_ip')
        if unbind_ip:
            PodCollection._remove_public_ip(ip=unbind_ip)
        return net.to_dict()

    def get_user_addresses(self, user):
        pods = dict([(pod.id, pod.name)
            for pod in user.pods if pod.status != 'deleted'])
        return [{
                'id': str(ipaddress.ip_address(i.ip_address)),
                'pod': pods[i.pod_id]
            } for i in PodIP.filter(PodIP.pod_id.in_(pods.keys()))]

    @atomic(nested=False)
    def delete(self, network):
        network = str(ip_network(network))
        if not IPPool.filter_by(network=network).first():
            raise APIError("Network '{0}' does not exist".format(network), 404)
        podip = PodIP.filter_by(network=network).first()
        if podip is not None:
            raise APIError("You cannot delete this network '{0}' while "
                           "some of IP-addresses of this network were "
                           "assigned to Pods".format(network))
        IPPool.query.filter_by(network=network).delete()

    def _parse_autoblock(self, data):
        blocklist = set()
        if not data:
            return blocklist
        for num in [i.strip() for i in data.split(',')]:
            if num.isdigit():
                blocklist.add(int(num))
                continue
            try:
                f, l = map(int, num.split('-'))
                blocklist.update(set(range(f, l+1)))
            except ValueError:
                continue
        return blocklist
