from collections import namedtuple
from ..core import db
from ..users.models import User
from ..utils import send_event_to_user, send_event_to_role
from ..models_mixin import BaseModelMixin

# Package and Kube with id=0 are default
DEFAULT_KUBE_TYPE = 1

#: Special kube type for internal services
INTERNAL_SERVICE_KUBE_TYPE = -1

#: Special kube types for internal usage
# Pods with these kube types must be excluded from billing.
NOT_PUBLIC_KUBE_TYPES = {INTERNAL_SERVICE_KUBE_TYPE}

Limits = namedtuple('Limits', ['cpu', 'memory', 'disk_space'])


class PackageKube(BaseModelMixin, db.Model):
    __tablename__ = 'package_kube'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), nullable=False)
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'), nullable=False)
    kube_price = db.Column(db.Float, default=0.0, nullable=False)

    kube = db.relationship('Kube', backref='packages')
    package = db.relationship('Package', backref='kubes')

    def to_dict(self):
        return {field: getattr(self, field)
                for field in ('package_id', 'kube_id', 'kube_price')}


class Package(BaseModelMixin, db.Model):
    __tablename__ = 'packages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True, nullable=False)
    first_deposit = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default='USD', nullable=False)
    period = db.Column(db.String(16), default='hour', nullable=False)
    prefix = db.Column(db.String(16), default='', nullable=False)
    suffix = db.Column(db.String(16), default='', nullable=False)
    price_ip = db.Column(db.Float, default=0.0, nullable=False)
    price_pstorage = db.Column(db.Float, default=0.0, nullable=False)
    price_over_traffic = db.Column(db.Float, default=0.0, nullable=False)
    is_default = db.Column(db.Boolean, default=None)
    count_type = db.Column(db.String, nullable=False, default='fixed')

    __table_args__ = (db.Index('packages_is_default_key', 'is_default', unique=True,
                               postgresql_where=is_default.is_(True)),)

    users = db.relationship('User', backref='package')

    def to_dict(self, *args, **kwargs):
        with_kubes = kwargs.pop('with_kubes', False)
        with_internal = kwargs.pop('with_internal', False)
        data = super(Package, self).to_dict(*args, **kwargs)
        if with_kubes:
            data['kubes'] = [dict(package_kube.kube.to_dict(),
                                  price=package_kube.kube_price)
                             for package_kube in self.kubes]
            if with_internal:
                internal = Kube.query.get(INTERNAL_SERVICE_KUBE_TYPE)
                data['kubes'].append(dict(internal.to_dict(), price=0))
        return data

    @classmethod
    def by_name(cls, package_name):
        return cls.query.filter_by(name=package_name).first()

    @classmethod
    def remove_default_flags(cls):
        cls.query.update({Package.is_default: None}, synchronize_session='fetch')

    @classmethod
    def get_default(cls):
        return cls.query.filter(cls.is_default == True).first()


class Kube(BaseModelMixin, db.Model):
    __tablename__ = 'kubes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True, nullable=False)
    cpu = db.Column(db.Float, default=0.0, nullable=False)
    cpu_units = db.Column(db.String(32), default='Cores', nullable=False)
    memory = db.Column(db.Integer, default=0.0, nullable=False)
    memory_units = db.Column(db.String(3), default='MB', nullable=False)
    disk_space = db.Column(db.Integer, default=0, nullable=False)
    disk_space_units = db.Column(db.String(3), default='GB', nullable=False)
    included_traffic = db.Column(db.Integer, default=0, nullable=False)
    is_default = db.Column(db.Boolean, default=None)

    __table_args__ = (db.Index('one_default', 'is_default', unique=True,
                               postgresql_where=is_default.is_(True)),)

    nodes = db.relationship('Node', backref='kube')
    pods = db.relationship('Pod', backref='kube')

    def __repr__(self):
        return "<Kube(id='{0}', name='{1}')>".format(self.id, self.name)

    @property
    def available(self):
        """True if there are nodes for this kube type in the cluster."""
        return (self.id == Kube.get_internal_service_kube_type() or
                bool(self.nodes))

    def to_dict(self, include=None, exclude=()):
        return super(Kube, self).to_dict(
            include=dict(include or {}, available=self.available),
            exclude=exclude)

    @classmethod
    def get_by_id(cls, kubeid):
        return cls.query.filter(cls.id == kubeid).first()

    def to_limits(self, kubes=1):
        return Limits(kubes * self.cpu, kubes * self.memory, kubes * self.disk_space)

    @classmethod
    def get_by_name(cls, name, *additional_filters):
        """Searches for a kube by given name. Search is case insensitive."""
        query = cls.query.filter(
            db.func.lower(cls.name) == db.func.lower(name)
        )
        if additional_filters:
            query = query.filter(*additional_filters)
        return query.first()

    @classmethod
    def public_kubes(cls):
        return cls.query.filter(
            ~cls.id.in_(NOT_PUBLIC_KUBE_TYPES)
        ).order_by(cls.id)

    @staticmethod
    def is_kube_editable(kube_id):
        return kube_id not in NOT_PUBLIC_KUBE_TYPES

    def is_public(self):
        return self.id not in NOT_PUBLIC_KUBE_TYPES

    @classmethod
    def get_default_kube_type(cls):
        default_kube = cls.get_default_kube()
        if default_kube:
            return default_kube.id
        else:
            return DEFAULT_KUBE_TYPE

    @classmethod
    def get_default_kube(cls):
        return cls.query.filter(cls.is_default == True).first()

    @staticmethod
    def get_internal_service_kube_type():
        return INTERNAL_SERVICE_KUBE_TYPE

    @staticmethod
    def is_node_attachable_type(kube_type):
        return kube_type != INTERNAL_SERVICE_KUBE_TYPE

    def send_event(self, name):
        event_name, data = 'kube:{0}'.format(name), self.to_dict()
        for (user_id,) in db.session.query(User.id).filter(
                User.package_id.in_([p.package_id for p in self.packages])).all():
            send_event_to_user(event_name, data, user_id)
        send_event_to_role(event_name, data, 1)


class ExtraTax(BaseModelMixin, db.Model):
    __tablename__ = 'extra_taxes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    key = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(64), unique=True)
    price = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default="USD", nullable=False)
    period = db.Column(db.String(16), default="hour", nullable=False)
