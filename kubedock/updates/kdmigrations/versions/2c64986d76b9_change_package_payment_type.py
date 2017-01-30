
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

"""change package payment type

Revision ID: 2c64986d76b9
Revises: 42b36be03945
Create Date: 2016-03-24 14:24:33.167814

"""

# revision identifiers, used by Alembic.
revision = '2c64986d76b9'
down_revision = '42b36be03945'

from alembic import op


def upgrade():
    conn = op.get_bind()
    q = conn.execute("SELECT count_type FROM packages WHERE name='Standard package'")
    r = q.fetchall()
    if len(r) and len(r[0]) and r[0][0] is None:
        conn.execute("UPDATE packages SET count_type='fixed' WHERE name='Standard package'")
    op.alter_column('packages', 'count_type', nullable=False, server_default='fixed')


def downgrade():
    op.alter_column('packages', 'count_type', nullable=True, server_default=None)
