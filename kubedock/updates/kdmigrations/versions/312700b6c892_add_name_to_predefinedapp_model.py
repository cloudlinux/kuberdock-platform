
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

"""Add name to PredefinedApp model

Revision ID: 312700b6c892
Revises: 589e137e4b7c
Create Date: 2015-10-13 18:26:06.849909

"""

# revision identifiers, used by Alembic.
revision = '312700b6c892'
down_revision = '589e137e4b7c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('predefined_apps', sa.Column('name', sa.String(255),
                  server_default='', nullable=False))


def downgrade():
    op.drop_column('predefined_apps', 'name')
