
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

"""node missed actions

Revision ID: 18f6b46d5b6c
Revises: 38bc6f56f2aa
Create Date: 2015-09-25 16:18:31.492789

"""

# revision identifiers, used by Alembic.
revision = '18f6b46d5b6c'
down_revision = '38bc6f56f2aa'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('node_missed_actions',
                    sa.Column('host', sa.String(255), primary_key=True, nullable=False),
                    sa.Column('command', sa.Text, nullable=False),
                    sa.Column('time_stamp', sa.DateTime, primary_key=True, nullable=False))


def downgrade():
    op.drop_table('node_missed_actions')
