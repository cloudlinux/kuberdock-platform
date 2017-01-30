
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

"""add registered_hosts table

Revision ID: 442f26252e67
Revises: 4912523d89cb
Create Date: 2015-12-29 13:19:01.340214

"""

# revision identifiers, used by Alembic.
revision = '442f26252e67'
down_revision = '4912523d89cb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('registered_hosts',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False, autoincrement=True),
        sa.Column('host', sa.String, nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('time_stamp', sa.DateTime, nullable=False))


def downgrade():
        op.drop_table('registered_hosts')
