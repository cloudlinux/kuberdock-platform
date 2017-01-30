
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

from sqlalchemy import UniqueConstraint

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
    internal = db.Column(db.Boolean, nullable=False, default=False)
    users = db.relationship('User', backref='role', lazy='dynamic')
    permissions = db.relationship('Permission', backref='role', lazy='dynamic')

    def perms(self):
        resources = {r.id: r.name for r in Resource.all()}
        perms = [(p.name, resources[p.resource_id], p.allow)
                 for p in Permission.filter_by(role_id=self.id)]
        return perms

    @classmethod
    def by_rolename(cls, rolename):
        q = cls.query.filter(Role.rolename == rolename, db.not_(Role.internal))
        return q.first()

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

    __table_args__ = (UniqueConstraint('resource_id', 'role_id', 'name',
                                       name='resource_role_name_unique'),)

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
