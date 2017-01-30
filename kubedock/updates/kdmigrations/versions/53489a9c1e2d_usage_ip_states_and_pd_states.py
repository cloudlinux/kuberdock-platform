
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

"""Usage statistics: create tables for PersistentDiskState and IpState.

Revision ID: 53489a9c1e2d
Revises: 5173b3f01db4
Create Date: 2015-09-12 03:56:07.147548

"""

# revision identifiers, used by Alembic.
revision = '53489a9c1e2d'
down_revision = '5173b3f01db4'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table('pd_states',
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('pd_name', sa.String(), nullable=False),
                    sa.Column('size', sa.Integer(), nullable=False),
                    sa.Column('start_time', sa.DateTime(), nullable=False),
                    sa.Column('end_time', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
                    sa.PrimaryKeyConstraint('start_time'))
    op.create_table('ip_states',
                    sa.Column('pod_id', postgresql.UUID(), nullable=False),
                    sa.Column('ip_address', sa.BigInteger(), nullable=False),
                    sa.Column('start_time', sa.DateTime(), nullable=False),
                    sa.Column('end_time', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['pod_id'], ['pods.id']),
                    sa.PrimaryKeyConstraint('pod_id', 'start_time'))


def downgrade():
    op.drop_table('ip_states')
    op.drop_table('pd_states')
