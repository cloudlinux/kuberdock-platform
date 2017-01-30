
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

"""Add User.deleted column

Revision ID: 33ae2dd8e49b
Revises: 4fbcae87c090
Create Date: 2015-11-04 19:39:11.270502

"""

# revision identifiers, used by Alembic.
revision = '33ae2dd8e49b'
down_revision = '4fbcae87c090'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('users', sa.Column('deleted', sa.Boolean(),
                  nullable=False, server_default='False'))


def downgrade():
    op.drop_column('users', 'deleted')
