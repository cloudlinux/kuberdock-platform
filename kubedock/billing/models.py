from ..core import db

# Package and Kube with id=0 are default
# end must be undeletable (always present with id=0) for fallback
tags = db.Table('package_kube',
    db.Column('package_id', db.Integer, db.ForeignKey('packages.id')),
    db.Column('kube_id', db.Integer, db.ForeignKey('kubes.id'))
)

class Package(db.Model):
    __tablename__ = 'packages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True)
    amount = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default="USD", nullable=False)
    period = db.Column(db.String(16), default="hour", nullable=False)
    kubes = db.relationship('Kube', secondary=tags, backref=db.backref('packages', lazy='dynamic'))
    users = db.relationship("User", backref="package")

    def to_dict(self):
        return dict([(k, v) for k, v in vars(self).items() if not k.startswith('_')])


class Kube(db.Model):
    __tablename__ = 'kubes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True)
    cpu = db.Column(db.Float, default=0.0, nullable=False)
    cpu_units = db.Column(db.String(3), default='MHz', nullable=False)
    memory = db.Column(db.Integer, default=0.0, nullable=False)
    memory_units = db.Column(db.String(3), default='MB', nullable=False)
    disk_space = db.Column(db.Integer, default=0, nullable=False)
    total_traffic = db.Column(db.Integer, default=0, nullable=False)
    nodes = db.relationship('Node', backref='kube')

    def __repr__(self):
        return "<Kube(id='{0}', name='{1}')>".format(self.id, self.name)
    
    def to_dict(self):
        return dict([(k, v) for k, v in vars(self).items() if not k.startswith('_')])


class ExtraTax(db.Model):
    __tablename__ = 'extra_taxes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    key = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(64), unique=True)
    amount = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default="USD", nullable=False)
    period = db.Column(db.String(16), default="hour", nullable=False)

    def to_dict(self):
        return dict([(k, v) for k, v in vars(self).items() if not k.startswith('_')])
