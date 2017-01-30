
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

"""empty message

Revision ID: 46bba639e6fb
Revises: 27ac98113841
Create Date: 2016-02-05 07:06:29.186960

"""

# revision identifiers, used by Alembic.
revision = '46bba639e6fb'
down_revision = '27ac98113841'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('system_settings', sa.Column('options', sa.String(), nullable=True))


def downgrade():
    op.drop_column('system_settings', 'options')
