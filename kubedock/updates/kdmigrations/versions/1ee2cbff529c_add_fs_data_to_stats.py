
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

"""add fs_data to stats

Revision ID: 1ee2cbff529c
Revises: 3505518f6f4f
Create Date: 2015-10-30 20:23:23.182514

"""

# revision identifiers, used by Alembic.
revision = '1ee2cbff529c'
down_revision = '3505518f6f4f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('stat_wrap_5min', sa.Column('fs_data', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('stat_wrap_5min', 'fs_data')
