
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

"""Added impersonated_id to session_data

Revision ID: 11bf9b6a89b2
Revises: 3149fa6dc22b
Create Date: 2016-09-23 12:11:24.373622

"""

# revision identifiers, used by Alembic.
revision = '11bf9b6a89b2'
down_revision = '50451812ee04'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('session_data',
                  sa.Column('impersonated_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('session_data', 'impersonated_id')
