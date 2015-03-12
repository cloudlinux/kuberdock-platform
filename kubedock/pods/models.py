import ipaddress
from sqlalchemy.dialects import postgresql
from ..core import db
from ..models_mixin import BaseModelMixin
import signals


class Pod(db.Model):
    __tablename__ = 'pods'
    
    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    name = db.Column(db.String(length=255), unique=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    kubes = db.Column(db.Integer, nullable=False, default=1)
    config = db.Column(postgresql.JSON)
    status = db.Column(db.String(length=32), default='unknown')
    states = db.relationship('PodStates', backref='pod')
    
    def __repr__(self):
        return "<Pod(id='%s', name='%s', owner_id='%s', config='%s', status='%s')>" % (
            self.id, self.name, self.owner_id, self.config, self.status)


class PodStates(db.Model):
    __tablename__ = 'pod_states'
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'), primary_key=True, nullable=False)
    start_time = db.Column(db.Integer, primary_key=True, nullable=False)
    end_time = db.Column(db.Integer, nullable=True)
    
    def __repr__(self):
        return "<Pod(pod_id='%s', start_time='%s', end_time='%s')>" % (
            self.pod_id, self.start_time, self.end_time)

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

    def __repr__(self):
        return self.network

    def hosts(self, as_int=None, as_str=None):
        network = self.network
        if not self.ipv6 and network.find('/') < 0:
            network = u'{0}/32'.format(network)
        _hosts = ipaddress.ip_network(unicode(network))
        if as_int:
            return [int(h) for h in _hosts]
        elif as_str:
            return [str(h) for h in _hosts]
        return _hosts

    def free_hosts(self, as_int=None, as_str=None):
        allocated_ips = [pod.ip_address
                         for pod in PodIP.filter_by(network=self.network)]
        _hosts = self.hosts()
        for ip in allocated_ips:
            _hosts = _hosts.address_exclude(ipaddress.ip_network(ip))
        if as_int:
            return [int(h) for h in _hosts]
        elif as_str:
            return [str(h) for h in _hosts]
        return _hosts

    def free_hosts_and_busy(self, as_int=None):
        pods = PodIP.filter_by(network=self.network)
        allocated_ips = {int(pod) if as_int else str(pod): pod.get_pod()
                         for pod in pods}
        data = []
        for ip in self.hosts(as_str=not as_int):
            data.append((ip, allocated_ips.get(ip)))
        data.sort()
        return data

    @property
    def is_free(self):
        return len(self.free_hosts(as_int=True)) > 0

    def to_dict(self, include=None, exclude=None):
        data = self.free_hosts_and_busy()
        data = dict(
            network=self.network,
            ipv6=self.ipv6,
            free_hosts=self.free_hosts(as_str=True),
            allocation=data
        )
        return data

    @classmethod
    def has_public_ips(cls):
        for n in cls.all():
            if n.is_free:
                return True
        return False

    @classmethod
    def get_free(cls):
        for n in cls.all():
            if n.is_free:
                return n
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
    def allocate_ip_address(cls, pid, network=None, add_network=None):
        """
        Allocate an IP-address to POD
        :param pid: Pod Id
        :param network: (optional) Selected network (pool)
        :return: PodIP object
        """
        pod = Pod.query.filter_by(id=pid).first()
        if pod is None:
            raise Exception("Wrong Pod Id '{0}".format(pid))
        pool = None
        if network is None:
            pool = IPPool.filter_by(is_free=True).first()
        elif isinstance(network, basestring):
            pool = IPPool.filter_by(network=network).first()
        if pool is None:
            if add_network and network:
                pool, created = IPPool.get_or_create(
                    network=str(ipaddress.ip_network(unicode(network))))
                if created:
                    pool.save()
            pool = IPPool.get_free()
            if pool is None:
                raise Exception(
                    'There are no free networks to allocate IP-address')
        free_hosts = pool.free_hosts(as_int=True)
        if not free_hosts:
            raise Exception('There are no free IP-addresses')
        podip = cls.filter_by(pod_id=pid).first()
        if podip is None:
            podip = cls.create(pod_id=pid, network=pool.network,
                               ip_address=free_hosts[0])
            podip.save()
        return podip

    def get_pod(self):
        return Pod.query.get(self.pod_id).name

    def to_dict(self, include=None, exclude=None):
        ip = self.ip_address
        return dict(
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
        args = (args[0], None, None)
    elif len(args) == 2:
        args = (args[0], args[1], None)
    pid, network, add_network = args
    return PodIP.allocate_ip_address(pid, network, add_network)
