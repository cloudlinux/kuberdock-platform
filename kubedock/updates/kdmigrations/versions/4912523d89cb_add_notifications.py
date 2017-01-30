
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

"""add notifications

Revision ID: 4912523d89cb
Revises: 56ab56a9ac5
Create Date: 2015-12-28 13:57:36.687236

"""

# revision identifiers, used by Alembic.
revision = '4912523d89cb'
down_revision = '56ab56a9ac5'

from alembic import op
import sqlalchemy as sa

Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


class Role(Base):
    __tablename__ = 'rbac_role'

    id = sa.Column(sa.Integer, primary_key=True)
    rolename = sa.Column(sa.String(64), unique=True)
    internal = sa.Column(sa.Boolean, nullable=False, default=False)


class RoleForNotification(Base):
    __tablename__ = 'notification_roles'
    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    nid = sa.Column(sa.Integer, sa.ForeignKey('notifications.id'), primary_key=True, nullable=False)
    rid = sa.Column(sa.Integer, sa.ForeignKey('rbac_role.id'), primary_key=True, nullable=False)
    target = sa.Column(sa.String(255))
    time_stamp = sa.Column(sa.DateTime)
    role = sa.orm.relationship('Role')


class Notification(Base):
    __tablename__ = 'notifications'
    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True, nullable=False)
    type = sa.Column(sa.String(12), nullable=False)
    message = sa.Column(sa.String(255), nullable=False, unique=True)
    description = sa.Column(sa.Text, nullable=False)
    roles = sa.orm.relationship('RoleForNotification')


class SystemSettings(Base):
    __tablename__ = 'system_settings'

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    name = sa.Column(sa.String(255), nullable=False, unique=True)
    value = sa.Column(sa.Text, nullable=True)
    label = sa.Column(sa.String, nullable=True)
    description = sa.Column(sa.Text, nullable=True)
    placeholder = sa.Column(sa.String, nullable=True)


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    session = Session(bind=bind)
    session._model_changes = False  # workaround for Flask-SQLAlchemy

    m1 = Notification(type='warning',
                     message='LICENSE_EXPIRED',
                     description='Your license has been expired.')
    m2 = Notification(type='warning',
                     message='NO_LICENSE',
                     description='License not found.')

    session.add_all([m1, m2])
    smtp = session.query(SystemSettings).filter_by(name='default_smtp_server').first()
    if smtp is not None:
        session.delete(smtp)
    session.commit()


def downgrade():
    op.drop_table('notification_roles')
    op.drop_table('notifications')
