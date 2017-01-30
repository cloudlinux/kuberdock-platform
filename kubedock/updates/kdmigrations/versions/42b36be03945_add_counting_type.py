
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

"""add counting type

Revision ID: 42b36be03945
Revises: 27c8f4c5f242
Create Date: 2016-03-10 10:28:03.769798

"""

# revision identifiers, used by Alembic.
revision = '42b36be03945'
down_revision = '27c8f4c5f242'

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('packages', sa.Column('count_type', sa.String, nullable=True))
    op.alter_column('stat_wrap_5min', 'fs_data', type_=sa.Text)


def downgrade():
    op.drop_column('packages', 'count_type')
    op.alter_column('stat_wrap_5min', 'fs_data', type_=sa.String(255))
