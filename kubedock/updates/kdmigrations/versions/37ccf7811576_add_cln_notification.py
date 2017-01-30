
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

"""Add CLN_NOTIFICATION

Revision ID: 37ccf7811576
Revises: 442f26252e67
Create Date: 2015-12-31 13:56:55.531181

"""

# revision identifiers, used by Alembic.
revision = '37ccf7811576'
down_revision = '442f26252e67'

from alembic import op
import sqlalchemy as sa


Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


class Notification(Base):
    __tablename__ = 'notifications'
    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True, nullable=False)
    type = sa.Column(sa.String(12), nullable=False)
    message = sa.Column(sa.String(255), nullable=False, unique=True)
    description = sa.Column(sa.Text, nullable=False)


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    session._model_changes = False  # workaround for Flask-SQLAlchemy

    m1 = Notification(type='info',
                     message='CLN_NOTIFICATION',
                     description='')
    session.add(m1)
    session.commit()


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    session._model_changes = False  # workaround for Flask-SQLAlchemy
    m = session.query(Notification).filter_by(message='CLN_NOTIFICATION').first()
    if m is not None:
        session.delete(m)
    session.commit()
