from ..core import db
from ..models_mixin import BaseModelMixin


class Resource(BaseModelMixin, db.Model):
    __tablename__ = 'rbac_resource'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = db.Column(db.String(128), unique=True, nullable=False)
    permissions = db.relationship(
        'Permission', backref='resource', lazy='dynamic')

    def __repr__(self):
        return "<Resource(name='{0}')>".format(self.name)

    def to_dict(self):
        return dict(id=self.id, name=self.name)


class Role(BaseModelMixin, db.Model):
    __tablename__ = 'rbac_role'

    id = db.Column(db.Integer, primary_key=True)
    rolename = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')
    permissions = db.relationship('Permission', backref='role', lazy='dynamic')

    def perms(self):
        resources = {r.id: r.name for r in Resource.all()}
        perms = [(p.name, resources[p.resource_id], p.allow)
                 for p in Permission.filter_by(role_id=self.id)]
        return perms

    @classmethod
    def by_rolename(cls, rolename):
        return cls.query.filter_by(rolename=rolename).first()

    def __repr__(self):
        return "<Role(rolename='{0}')>".format(self.rolename)

    def to_dict(self):
        return dict(id=self.id, rolename=self.rolename)


class Permission(BaseModelMixin, db.Model):
    __tablename__ = 'rbac_permission'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('rbac_resource.id'))
    role_id = db.Column(db.Integer, db.ForeignKey('rbac_role.id'))
    name = db.Column(db.String(64), unique=False)
    allow = db.Column(db.Boolean, default=True)

    def to_dict(self, include=None, exclude=None):
        data = dict(
            id=self.id, resource_id=self.resource_id, role_id=self.role_id,
            name=self.name, allow=self.allow
        )
        return data

    def set_allow(self):
        self.allow = True
        self.save()

    def set_deny(self):
        self.allow = False
        self.save()

    def __repr__(self):
        return "<Permission(name='{0}', allow={1})>".format(
            self.name, self.allow)
