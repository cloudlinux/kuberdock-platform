import json
import ipaddress
import random
import string
from sqlalchemy.dialects import postgresql
from flask import current_app
from ..core import db
from ..models_mixin import BaseModelMixin
from .. import signals
from ..billing.models import Package


class Pod(db.Model):
    __tablename__ = 'pods'

    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    name = db.Column(db.String(length=255), unique=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    config = db.Column(db.Text)
    status = db.Column(db.String(length=32), default='unknown')
    states = db.relationship('ContainerState', backref='pod')

    def __repr__(self):
        return "<Pod(id='%s', name='%s', owner_id='%s', kubes='%s', config='%s', status='%s')>" % (
            self.id, self.name, self.owner_id, self.kubes, self.config, self.status)

    @property
    def kubes(self):
        return sum(
            [c.get('kubes', 1) for c in json.loads(self.config)['containers']]
        )

    @property
    def is_deleted(self):
        return self.status == 'deleted'

    @property
    def containers_count(self):
        return len(json.loads(self.config).get('containers', []))

    @property
    def price_per_hour(self):
        return self.kubes * self.kube.price

    def delete(self):
        self.name += '__' + ''.join(random.sample(string.lowercase + string.digits, 8))
        self.status = 'deleted'


class ContainerState(db.Model):
    __tablename__ = 'container_states'
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'), primary_key=True, nullable=False)
    container_name = db.Column(db.String(length=255), primary_key=True, nullable=False)
    kubes = db.Column(db.Integer, primary_key=True, nullable=False, default=1)
    start_time = db.Column(db.DateTime, primary_key=True, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return "<ContainerState(pod_id='%s', container_name='%s', kubes='%s', start_time='%s', end_time='%s')>" % (
            self.pod_id, self.container_name, self.kubes, self.start_time, self.end_time)

class ImageCache(db.Model):
    __tablename__ = 'image_cache'

    query = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return "<ImageCache(query='%s', data='%s', time_stamp='%s'')>" % (
            self.query, self.data, self.time_stamp)


class DockerfileCache(db.Model):
    __tablename__ = 'dockerfile_cache'

    image = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return "<DockerfileCache(image='%s', data='%s', time_stamp='%s'')>" % (
            self.image, self.data, self.time_stamp)


class IPPool(BaseModelMixin, db.Model):
    __tablename__ = 'ippool'

    network = db.Column(db.String, primary_key=True, nullable=False)
    ipv6 = db.Column(db.Boolean, default=False)
    blocked_list = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return self.network

    def get_blocked_list(self, as_int=None):
        blocked_list = []
        try:
            blocked_list = json.loads(self.blocked_list or "[]")
            if as_int is None:
                blocked_list = [str(ipaddress.ip_address(int(ip)))
                                for ip in blocked_list]
            blocked_list.sort()
        except Exception, e:
            current_app.logger.warning("IPPool.get_blocked_list failed: "
                                       "{0}".format(e))
        return blocked_list

    def block_ip(self, ip):
        blocked_list = self.get_blocked_list(as_int=True)
        if isinstance(ip, (tuple, list, set)):
            for _ip in ip:
                if _ip not in blocked_list:
                    blocked_list.append(_ip)
        else:
            if ip not in blocked_list:
                blocked_list.append(int(ipaddress.ip_address(ip)))
        self.blocked_list = json.dumps(blocked_list)
        self.save()

    def unblock_ip(self, ip):
        if isinstance(ip, basestring):
            ip = int(ipaddress.ip_address(ip))
        blocked_list = self.get_blocked_list(as_int=True)
        if ip not in blocked_list:
            return
        ind = blocked_list.index(ip)
        if ind >= 0:
            del blocked_list[ind]
        self.blocked_list = json.dumps(blocked_list)
        self.save()

    def hosts(self, as_int=None, exclude=None, allowed=None):
        """
        Return IPv4Network object or list of IPs (long) or list of IPs (string)
        :param as_int: Return list of IPs (long)
        :param exclude: Exclude IP from IP list (list, tuple, str, int)
        :return: IPv4Network or list
        """
        network = self.network
        if not self.ipv6 and network.find('/') < 0:
            network = u'{0}/32'.format(network)
        network = ipaddress.ip_network(unicode(network))
        hosts = list(network.hosts()) or [network.network_address]
        if exclude:
            if isinstance(exclude, (basestring, int)):
                hosts = [h for h in hosts if int(h) != int(exclude)]
            elif isinstance(exclude, (list, tuple)):
                hosts = [h for h in hosts
                         if int(h) not in [int(ex) for ex in exclude]]
        if as_int:
            hosts = [int(h) for h in hosts]
        else:
            hosts = [str(h) for h in hosts]
        hosts.sort()
        return hosts

    def free_hosts(self, as_int=None):
        ip_list = [pod.ip_address
                   for pod in PodIP.filter_by(network=self.network)]
        ip_list = list(set(ip_list) | set(self.get_blocked_list(as_int=True)))
        _hosts = self.hosts(as_int=as_int, exclude=ip_list)
        return _hosts

    def free_hosts_and_busy(self, as_int=None):
        pods = PodIP.filter_by(network=self.network)
        allocated_ips = {int(pod): pod.get_pod() for pod in pods}
        data = []
        blocked_list = self.get_blocked_list(as_int=True)
        hosts = self.hosts(as_int=True)
        for ip in hosts:
            pod = allocated_ips.get(ip)
            status = 'blocked' \
                if ip in blocked_list else 'busy' if pod else 'free'
            if not as_int:
                ip = str(ipaddress.ip_address(ip))
            data.append((ip, pod, status))
        data.sort()
        return data

    @property
    def is_free(self):
        return len(self.free_hosts(as_int=True)) > 0

    def get_first_free_host(self, as_int=None):
        free_hosts = self.free_hosts(as_int=as_int)
        if free_hosts:
            return free_hosts[0]
        return None

    @classmethod
    def get_network_by_ip(cls, ip_address):
        ip_address = ipaddress.ip_address(ip_address)
        for net in cls.all():
            if ip_address in ipaddress.ip_network(net.network).hosts():
                return net
        return None

    def to_dict(self, include=None, exclude=None):
        free_hosts_and_busy = self.free_hosts_and_busy()
        data = dict(
            id=self.network,
            network=self.network,
            ipv6=self.ipv6,
            free_hosts=self.free_hosts(),
            blocked_list=self.get_blocked_list(),
            allocation=free_hosts_and_busy
        )
        return data

    @classmethod
    def has_public_ips(cls):
        for n in cls.all():
            if n.is_free:
                return True
        return False

    @classmethod
    def get_free_host(cls, as_int=None):
        for n in cls.all():
            free_host = n.get_first_free_host(as_int=as_int)
            if free_host is not None:
                return free_host
        return None


class PodIP(BaseModelMixin, db.Model):
    __tablename__ = 'podip'

    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'),
                       primary_key=True, nullable=False)
    network = db.Column(db.ForeignKey('ippool.network'))
    ip_address = db.Column(db.BigInteger, nullable=False)

    def __str__(self):
        return str(ipaddress.ip_address(self.ip_address))

    def __int__(self):
        return self.ip_address

    @classmethod
    def allocate_ip_address(cls, pid, ip_address=None):
        """
        Allocate an IP-address to POD
        :param pid: Pod Id
        :param network: (optional) Selected network (pool)
        :return: PodIP object
        """
        pod = Pod.query.filter_by(id=pid).first()
        if pod is None:
            raise Exception("Wrong Pod Id '{0}".format(pid))
        network = None
        if ip_address is None:
            ip_address = IPPool.get_free_host(as_int=True)
            if ip_address is None:
                raise Exception('There are no free IP-addresses')
        else:
            network = IPPool.get_network_by_ip(ip_address)
        if ip_address is None:
            raise Exception('There are no free networks to allocate IP-address')
        if network is None:
            raise Exception(
                'Cannot find network by IP-address: {0}'.format(ip_address))
        if isinstance(ip_address, basestring):
            ip_address = int(ipaddress.ip_address(ip_address))
        podip = cls.filter_by(pod_id=pid).first()
        if podip is None:
            podip = cls.create(pod_id=pid, network=network.network,
                               ip_address=ip_address)
            podip.save()
        return podip

    def get_pod(self):
        return Pod.query.get(self.pod_id).name

    def to_dict(self, include=None, exclude=None):
        ip = self.ip_address
        return dict(
            id=self.pod_id,
            pod_id=self.pod_id,
            network=self.network.network,
            ip_address_int=ip,
            ip_address=ipaddress.ip_address(ip)
        )


###############
### Signals ###
@signals.allocate_ip_address.connect
def allocate_ip_address_signal(args):
    if len(args) == 1:
        args = (args[0], None)
    pid, network = args
    return PodIP.allocate_ip_address(pid, network)
