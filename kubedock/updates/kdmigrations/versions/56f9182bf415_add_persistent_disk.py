
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

"""Add PersistetnDisk

Revision ID: 56f9182bf415
Revises: 1ee2cbff529c
Create Date: 2015-11-02 01:34:40.942580

"""

# revision identifiers, used by Alembic.
revision = '56f9182bf415'
down_revision = '1ee2cbff529c'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        'persistent_disk',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('drive_name', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('pod_id', postgresql.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['pod_id'], ['pods.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('drive_name'),
        sa.UniqueConstraint('name', 'owner_id')
    )


def downgrade():
    op.drop_table('persistent_disk')
