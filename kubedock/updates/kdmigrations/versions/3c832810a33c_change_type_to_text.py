
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

"""change type to text

Revision ID: 3c832810a33c
Revises: 45e4b1e232ad
Create Date: 2016-05-16 09:55:57.788558

"""

# revision identifiers, used by Alembic.
revision = '3c832810a33c'
down_revision = '220dacf65cba'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('notification_roles', 'target', type_=sa.Text)
    op.alter_column('notifications', 'message', type_=sa.Text)


def downgrade():
    op.alter_column('notification_roles', 'target', type_=sa.String(255))
    op.alter_column('notifications', 'message', type_=sa.String(255))
