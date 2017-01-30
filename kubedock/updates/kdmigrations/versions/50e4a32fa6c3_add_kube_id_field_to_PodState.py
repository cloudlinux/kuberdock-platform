
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

"""Add kube_id field to PodState

Revision ID: 50e4a32fa6c3
Revises: 3149fa6dc22b
Create Date: 2016-10-14 15:48:59.602985

"""

# revision identifiers, used by Alembic.
revision = '50e4a32fa6c3'
down_revision = '81398dd39d6'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects import postgresql

Base = declarative_base()


class Pod(Base):
    __tablename__ = 'pods'
    id = sa.Column(postgresql.UUID, primary_key=True, nullable=False)
    kube_id = sa.Column(sa.Integer)


class PodState(Base):
    __tablename__ = 'pod_states'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True,
                   nullable=False)
    pod_id = sa.Column(postgresql.UUID, nullable=False)
    kube_id = sa.Column(sa.Integer, nullable=False)


def upgrade():
    op.add_column('pod_states', sa.Column('kube_id', sa.Integer(),
                                          nullable=True))

    session = sa.orm.sessionmaker()(bind=op.get_bind())
    for (pod_id, kube_id) in session.query(Pod.id, Pod.kube_id):
        session.query(PodState).filter_by(pod_id=pod_id).update(
            {'kube_id': kube_id})
    session.commit()

    op.alter_column('pod_states', 'kube_id', nullable=False)


def downgrade():
    op.drop_column('pod_states', 'kube_id')
