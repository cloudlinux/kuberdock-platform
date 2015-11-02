import json
import ipaddress
import random
import string
import types
from datetime import datetime
from hashlib import md5
from sqlalchemy.dialects import postgresql
from flask import current_app
from ..core import db
from ..settings import DOCKER_IMG_CACHE_TIMEOUT
from ..models_mixin import BaseModelMixin
from .. import signals
from ..usage.models import IpState
from ..users.models import User
from ..kapi import pd_utils


class Pod(BaseModelMixin, db.Model):
    __tablename__ = 'pods'
    __table_args__ = (db.UniqueConstraint('name', 'owner_id'),)

    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    name = db.Column(db.String(length=255))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    # Not a foreignkey because templates may be deleted at any time
    template_id = db.Column(db.Integer, nullable=True)
    config = db.Column(db.Text)
    status = db.Column(db.String(length=32), default='unknown')

    def __repr__(self):
        return "<Pod(id='%s', name='%s', owner_id='%s', kubes='%s', config='%s', status='%s')>" % (
            self.id, self.name.encode('ascii', 'replace'), self.owner_id, self.kubes, self.config, self.status)

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
        if self.kube is None:
            return 0
        return self.kubes * self.kube.price

    @property
    def namespace(self):
        try:
            config = json.loads(self.config)
            if 'namespace' in config:
                return config['namespace']
        except Exception, e:
            current_app.logger.warning('Pod.namespace failed: {0}'.format(e))
        return 'default'

    @property
    def is_default_ns(self):
        return self.namespace == 'default'

    def delete(self):
        self.name += '__' + ''.join(random.sample(string.lowercase + string.digits, 8))
        self.status = 'deleted'

    def to_dict(self):
        return dict(
            id=self.id,
            name=self.name,
            kube=self.kube.to_dict(),
            owner=self.owner.to_dict(),
            config=json.loads(self.config),
            status=self.status)


class ImageCache(db.Model):
    __tablename__ = 'image_cache'

    query = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return "<ImageCache(query='%s', data='%s', time_stamp='%s'')>" % (
            self.query, self.data, self.time_stamp)

    @property
    def outdated(self):
        return (datetime.utcnow() - self.time_stamp) > DOCKER_IMG_CACHE_TIMEOUT


class DockerfileCache(db.Model):
    __tablename__ = 'dockerfile_cache'

    image = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return "<DockerfileCache(image='%s', data='%s', time_stamp='%s'')>" % (
            self.image, self.data, self.time_stamp)

    @property
    def outdated(self):
        return (datetime.utcnow() - self.time_stamp) > DOCKER_IMG_CACHE_TIMEOUT


def _page(page, pages):
    if page is None or page < 1:
        page = 1
    elif page > pages:
        page = pages
    return page


def _ip_network_hosts(obj, page=None):
    pages = obj.pages()
    page = _page(page, pages)
    net_ip = obj.network_address + (page - 1) * 2 ** obj.page_bits
    net_pl = obj.max_prefixlen - obj.page_bits if pages > 1 else obj.prefixlen
    network = ipaddress.ip_network(u'{0}/{1}'.format(net_ip, net_pl))
    return network.hosts()


def _ip_network_iterpages(obj):
    return xrange(1, obj.pages() + 1)


def _ip_network_pages(obj):
    suf_len = obj.max_prefixlen - obj.prefixlen
    pages = 2 ** (suf_len - obj.page_bits) if suf_len > obj.page_bits else 1
    return pages


def ip_network(network):
    ip_net_obj = ipaddress.ip_network(network)
    ip_net_obj.page_bits = 8
    ip_net_obj.hosts = types.MethodType(_ip_network_hosts, ip_net_obj)
    ip_net_obj.iterpages = types.MethodType(_ip_network_iterpages, ip_net_obj)
    ip_net_obj.pages = types.MethodType(_ip_network_pages, ip_net_obj)
    return ip_net_obj


class IPPool(BaseModelMixin, db.Model):
    __tablename__ = 'ippool'

    network = db.Column(db.String, primary_key=True, nullable=False)
    ipv6 = db.Column(db.Boolean, default=False)
    blocked_list = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return self.network

    def iterpages(self):
        return ip_network(self.network).iterpages()

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

    def hosts(self, as_int=None, exclude=None, allowed=None, page=None):
        """
        Return IPv4Network object or list of IPs (long) or list of IPs (string)
        :param as_int: Return list of IPs (long)
        :param exclude: Exclude IP from IP list (list, tuple, str, int)
        :return: IPv4Network or list
        """
        network = self.network
        if not self.ipv6 and network.find('/') < 0:
            network = u'{0}/32'.format(network)
        network = ip_network(unicode(network))
        hosts = list(network.hosts(page=page)) or [network.network_address]
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
        return hosts

    def free_hosts(self, as_int=None, page=None):
        ip_list = [pod.ip_address
                   for pod in PodIP.filter_by(network=self.network)]
        ip_list = list(set(ip_list) | set(self.get_blocked_list(as_int=True)))
        _hosts = self.hosts(as_int=as_int, exclude=ip_list, page=page)
        return _hosts

    def free_hosts_and_busy(self, as_int=None, page=None):
        pods = PodIP.filter_by(network=self.network)
        allocated_ips = {int(pod): pod.get_pod() for pod in pods}
        data = []
        blocked_list = self.get_blocked_list(as_int=True)
        hosts = self.hosts(as_int=True, page=page)
        for ip in hosts:
            pod = allocated_ips.get(ip)
            status = 'blocked' \
                if ip in blocked_list else 'busy' if pod else 'free'
            if not as_int:
                ip = str(ipaddress.ip_address(ip))
            data.append((ip, pod, status))
        return data

    @property
    def is_free(self):
        for page in self.iterpages():
            if len(self.free_hosts(as_int=True, page=page)) > 0:
                return True
        return False

    def get_first_free_host(self, as_int=None):
        for page in self.iterpages():
            free_hosts = self.free_hosts(as_int=as_int, page=page)
            if free_hosts:
                return free_hosts[0]
        return None

    @classmethod
    def get_network_by_ip(cls, ip_address):
        ip_address = ipaddress.ip_address(ip_address)
        for net in cls.all():
            network = ip_network(net.network)
            for page in network.iterpages():
                if ip_address in network.hosts(page=page):
                    return net
        return None

    def to_dict(self, include=None, exclude=None, page=None):
        free_hosts_and_busy = self.free_hosts_and_busy(page=page)
        pages = ip_network(self.network).pages()
        page = _page(page, pages)
        data = dict(
            id=self.network,
            network=self.network,
            ipv6=self.ipv6,
            free_hosts=self.free_hosts(page=page),
            blocked_list=self.get_blocked_list(),
            allocation=free_hosts_and_busy,
            page=page,
            pages=pages,
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
    pod = db.relationship(Pod)
    network = db.Column(db.ForeignKey('ippool.network'))
    ip_address = db.Column(db.BigInteger, nullable=False)

    def __str__(self):
        return str(ipaddress.ip_address(self.ip_address))

    def __int__(self):
        return self.ip_address

    def save(self):
        IpState.start(self.pod_id, self.ip_address)
        return super(PodIP, self).save()

    def delete(self):
        IpState.end(self.pod_id, self.ip_address)
        return super(PodIP, self).delete()

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


class PersistentDisk(BaseModelMixin, db.Model):
    __tablename__ = 'persistent_disk'
    __table_args__ = (
        db.UniqueConstraint('drive_name'),
        db.UniqueConstraint('name', 'owner_id'),
    )

    id = db.Column(db.String(32), primary_key=True, nullable=False)
    drive_name = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    owner_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship(User)
    size = db.Column(db.BigInteger, nullable=False)
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'), nullable=True)
    pod = db.relationship(Pod)

    def __init__(self, *args, **kwargs):
        super(PersistentDisk, self).__init__(*args, **kwargs)
        if self.drive_name is None:
            owner = self.owner if self.owner is not None else self.owner_id
            self.drive_name = pd_utils.compose_pdname(self.name, owner)
        if self.id is None:
            self.id = md5(self.drive_name).hexdigest()

    def __str__(self):
        return ('PersistentDisk(drive_name={0}, name={1}, owner={2}, size={3}, pod={4})'
                .format(self.drive_name, self.name, self.owner, self.size, self.pod))

    @classmethod
    def take(cls, pod_id, drives):
        db.session.begin_nested()
        cls.filter(cls.drive_name.in_(drives), cls.pod_id.is_(None)).update(
            {'pod_id': pod_id}, synchronize_session=False)
        already_taken = cls.filter(cls.drive_name.in_(drives),
                                   cls.pod_id != pod_id).first()
        if already_taken:
            db.session.rollback()
            db.session.refresh(already_taken)
            return already_taken
        db.session.commit()

    @classmethod
    def free(cls, pod_id):
        return cls.filter_by(pod_id=pod_id).update({cls.pod_id: None})

    def to_dict(self):
        return dict(id=self.id,
                    drive_name=self.drive_name,
                    name=self.name,
                    owner=self.owner.username,
                    size=self.size,
                    pod=self.pod_id,
                    in_use=self.pod_id is not None)


class PrivateRegistryFailedLogin(BaseModelMixin, db.Model):
    """Stores time for last failed login attempts to private registries.
    It's a simple workaround to prevent blocking from a registry. It may occur
    when we frequently tried to login to a registry with the same name, and all
    attempts was failed. At the moment hub.docker.com blocks by name + IP if
    there were simultaneous failed login attempts.
    Just remember last failed login for name + registry here and do not allow
    next login attempt before some pause.

    """
    __tablename__ = 'private_registry_failed_login'

    login = db.Column(db.String(255), primary_key=True, nullable=False)
    registry = db.Column(db.String(255), primary_key=True, nullable=False)
    created = db.Column(db.DateTime, primary_key=True, nullable=False)


###############
### Signals ###
@signals.allocate_ip_address.connect
def allocate_ip_address_signal(args):
    if len(args) == 1:
        args = (args[0], None)
    pid, ip = args
    return PodIP.allocate_ip_address(pid, ip)
