
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

"""add direct access

Revision ID: 12963e26b673
Revises: 1a24688cc541
Create Date: 2016-07-01 06:33:38.183747

"""

# revision identifiers, used by Alembic.
revision = '12963e26b673'
down_revision = '1a24688cc541'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('pods', sa.Column('direct_access', sa.TEXT(), autoincrement=False, nullable=True))


def downgrade():
    op.drop_column('pods', 'direct_access')
