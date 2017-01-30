
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

"""PersistentDiskState.user_id nullable

Revision ID: 3a8320be841c
Revises: 1139a080f512
Create Date: 2015-10-20 07:17:08.792600

"""

# revision identifiers, used by Alembic.
revision = '3a8320be841c'
down_revision = '1139a080f512'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('pd_states', 'user_id',
                    existing_type=sa.INTEGER(), nullable=True)


def downgrade():
    op.alter_column('pd_states', 'user_id',
                    existing_type=sa.INTEGER(), nullable=False)
