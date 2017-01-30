
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

from ..core import db


class RoleForNotification(db.Model):
    __tablename__ = 'notification_roles'
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    nid = db.Column(db.Integer, db.ForeignKey('notifications.id'),
                    primary_key=True, nullable=False)
    rid = db.Column(db.Integer, db.ForeignKey('rbac_role.id'),
                    primary_key=True, nullable=False)
    target = db.Column(db.Text)
    time_stamp = db.Column(db.DateTime)
    role = db.relationship('Role')


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True,
                   nullable=False)
    type = db.Column(db.String(12), nullable=False)
    message = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    roles = db.relationship('RoleForNotification')
