from ..core import db

# Package and Kube with id=0 are default
# end must be undeletable (always present with id=0) for fallback


class Package(db.Model):
    __tablename__ = 'packages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True)
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    amount = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default="USD", nullable=False)
    period = db.Column(db.String(16), default="hour", nullable=False)
    users = db.relationship("User", backref="package")


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
    package = db.relationship('Package', backref='kube')
    nodes = db.relationship('Node', backref='kube')

    def __repr__(self):
        return "<Kube(id='{0}', name='{1}')>".format(self.id, self.name)