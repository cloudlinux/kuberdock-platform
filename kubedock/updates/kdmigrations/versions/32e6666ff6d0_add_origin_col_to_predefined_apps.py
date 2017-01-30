
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

"""add_origin_col_to_predefined_apps

Revision ID: 32e6666ff6d0
Revises: 46b5b819ba35
Create Date: 2015-12-10 16:48:47.775404

"""

# revision identifiers, used by Alembic.
revision = '32e6666ff6d0'
down_revision = '46b5b819ba35'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('predefined_apps', sa.Column('origin', sa.String(255),
                  nullable=False, server_default='unknown'))

def downgrade():
    op.drop_column('predefined_apps', 'origin')
