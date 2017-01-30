
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

Revision ID: 4078673e3670
Revises: 37ccf7811576
Create Date: 2016-01-14 07:38:44.472313

"""

# revision identifiers, used by Alembic.
revision = '4078673e3670'
down_revision = '37ccf7811576'

from alembic import op
import sqlalchemy as sa

Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


def upgrade():
    conn = op.get_bind()
    conn.execute("UPDATE packages SET period='month' WHERE id=0")


def downgrade():
    conn = op.get_bind()
    conn.execute("UPDATE packages SET period='hour' WHERE id=0")
