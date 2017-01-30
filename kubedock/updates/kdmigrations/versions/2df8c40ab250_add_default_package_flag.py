
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

"""Add is_default flag to packages

Revision ID: 2df8c40ab250
Revises: 46bba639e6fb
Create Date: 2016-02-09 22:21:55.489017

"""

# revision identifiers, used by Alembic.
revision = '2df8c40ab250'
down_revision = '46bba639e6fb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    op.add_column('packages', sa.Column('is_default', sa.Boolean(), nullable=True))
    op.create_unique_constraint(None, 'packages', ['is_default'])
    bind.execute("UPDATE packages SET is_default=true WHERE id in (SELECT MIN(id) FROM packages)")


def downgrade():
    op.drop_constraint('packages_is_default_key', 'packages', type_='unique')
    op.drop_column('packages', 'is_default')
