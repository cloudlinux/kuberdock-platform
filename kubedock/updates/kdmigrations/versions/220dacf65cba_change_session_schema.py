
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

"""change session schema

Revision ID: 220dacf65cba
Revises: 45e4b1e232ad
Create Date: 2016-05-09 14:23:42.761748

"""

# revision identifiers, used by Alembic.
revision = '220dacf65cba'
down_revision = '45e4b1e232ad'

from alembic import op
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    conn.execute("DELETE FROM session_data")
    op.drop_column('session_data', 'data')
    op.add_column('session_data', sa.Column('user_id', sa.Integer(), nullable=False))
    op.add_column('session_data', sa.Column('role_id', sa.Integer(), nullable=False))


def downgrade():
    op.drop_column('session_data', 'user_id')
    op.drop_column('session_data', 'role_id')
    op.add_column('session_data', sa.Column('data', sa.PickleType, nullable=True))
