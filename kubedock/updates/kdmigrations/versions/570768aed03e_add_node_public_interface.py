
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

"""Add Node.public_interface

Revision ID: 570768aed03e
Revises: 1f26cf5abc0f
Create Date: 2017-01-11 22:48:43.737880

"""

# revision identifiers, used by Alembic.
revision = '570768aed03e'
down_revision = '1f26cf5abc0f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('nodes', sa.Column('public_interface', sa.String(15),
                                     nullable=True))


def downgrade():
    op.drop_column('nodes', 'public_interface')
