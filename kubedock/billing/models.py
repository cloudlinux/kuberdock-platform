from ..core import db

#class Pricing(db.Model):
#    __tablename__ = 'pricing'
#    id = db.Column(db.Integer, unique=True, autoincrement=True, nullable=False)
#    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), primary_key=True)
#    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'), primary_key=True)
#    amount = db.Column(db.Float, default=0.0, nullable=False)
#    currency = db.Column(db.String(16), default="USD", nullable=False)
#    period = db.Column(db.String(16), default="hour", nullable=False)
#    package = db.relationship("Package", backref="package_assocs")
#    users = db.relationship("User", backref="pricing")
#
#class Kube(db.Model):
#    __tablename__ = 'kubes'
#    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
#    kube_name = db.Column(db.String(64), unique=True)
#    default = db.Column(db.Boolean, default=False, index=True)
#    packages = db.relationship('Pricing', backref='kube')
#
#class Package(db.Model):
#    __tablename__ = 'packages'
#    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
#    package_name = db.Column(db.String(64), unique=True)
#    default = db.Column(db.Boolean, default=False, index=True)
#    cpu = db.Column(db.Float, default=0.0, nullable=False)
#    cpu_units = db.Column(db.String(3), default='percent', nullable=False)
#    memory = db.Column(db.Integer, default=0.0, nullable=False)
#    memory_units = db.Column(db.String(3), default='percent', nullable=False)
#    disk_space = db.Column(db.Integer, default=0, nullable=False)
#    total_traffic = db.Column(db.Integer, default=0, nullable=False)

class Package(db.Model):
    __tablename__ = 'packages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False)
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    amount = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(16), default="USD", nullable=False)
    period = db.Column(db.String(16), default="hour", nullable=False)
    users = db.relationship("User", backref="package")
    
class Kube(db.Model):
    __tablename__ = 'kubes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    cpu = db.Column(db.Float, default=0.0, nullable=False)
    cpu_units = db.Column(db.String(3), default='MHz', nullable=False)
    memory = db.Column(db.Integer, default=0.0, nullable=False)
    memory_units = db.Column(db.String(3), default='MB', nullable=False)
    disk_space = db.Column(db.Integer, default=0, nullable=False)
    total_traffic = db.Column(db.Integer, default=0, nullable=False)
    package = db.relationship('Package', backref='kube')