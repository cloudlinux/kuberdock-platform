from ..core import db
#from ..nodes.models import Node

# Package and Kube with id=0 are default
# and must be undeletable (always present with id=0) for fallback


class PackageKube(db.Model):
    __tablename__ = 'package_kube'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'))
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    kube_price = db.Column(db.Float, default=0.0, nullable=False)

    kubes = db.relationship('Kube', backref=db.backref('packages_assocs'))
    packages = db.relationship('Package', backref=db.backref('kubes_assocs'))

    def to_dict(self):
        return {field: getattr(self, field)
                for field in ('package_id', 'kube_id', 'kube_price')}


class Package(db.Model):
    __tablename__ = 'packages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True)
    first_deposit = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default="USD", nullable=False)
    period = db.Column(db.String(16), default="hour", nullable=False)
    prefix = db.Column(db.String, default='', nullable=True)
    suffix = db.Column(db.String, default='', nullable=True)
    price_ip = db.Column(db.Float, default=0.0, nullable=False)
    price_pstorage = db.Column(db.Float, default=0.0, nullable=False)
    price_over_traffic = db.Column(db.Float, default=0.0, nullable=False)
    kubes = db.relationship('PackageKube', backref=db.backref('package'))
    users = db.relationship("User", backref="package")

    def to_dict(self):
        return {field: getattr(self, field) for field in self.__mapper__.columns.keys()}


class Kube(db.Model):
    __tablename__ = 'kubes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True)
    cpu = db.Column(db.Float, default=0.0, nullable=False)
    cpu_units = db.Column(db.String(32), default='Cores', nullable=False)
    memory = db.Column(db.Integer, default=0.0, nullable=False)
    memory_units = db.Column(db.String(3), default='MB', nullable=False)
    disk_space = db.Column(db.Integer, default=0, nullable=False)
    disk_space_units = db.Column(db.String(3), default='GB', nullable=False)
    included_traffic = db.Column(db.Integer, default=0, nullable=False)
    nodes = db.relationship('Node', backref='kube')
    pods = db.relationship('Pod', backref='kube')

    def __repr__(self):
        return "<Kube(id='{0}', name='{1}')>".format(self.id, self.name)

    def to_dict(self):
        return {field: getattr(self, field) for field in self.__mapper__.columns.keys()}


class ExtraTax(db.Model):
    __tablename__ = 'extra_taxes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    key = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(64), unique=True)
    price = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default="USD", nullable=False)
    period = db.Column(db.String(16), default="hour", nullable=False)

    def to_dict(self):
        return dict([(k, v) for k, v in vars(self).items() if not k.startswith('_')])
