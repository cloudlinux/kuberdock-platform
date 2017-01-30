
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

Revision ID: 3d2db4a87f86
Revises: 5049471549ba
Create Date: 2015-11-10 21:58:22.428392

"""

# revision identifiers, used by Alembic.
revision = '3d2db4a87f86'
down_revision = '5049471549ba'

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('rbac_role', sa.Column('internal', sa.Boolean(),
                                         nullable=False,
                                         server_default='False'))


def downgrade():
    op.drop_column('rbac_role', 'internal')
