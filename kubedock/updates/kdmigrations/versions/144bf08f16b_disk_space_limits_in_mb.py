
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

"""Disk space limits in MB

Revision ID: 144bf08f16b
Revises: None
Create Date: 2015-08-17 11:15:40.550755

"""

revision = '144bf08f16b'
down_revision = None

from alembic import op
import sqlalchemy as sa


from kubedock.billing.models import Kube


def upgrade():
    op.add_column('kubes', sa.Column('disk_space_units', sa.String(3),
                  server_default='MB', nullable=False))

    session = sa.orm.sessionmaker()(bind=op.get_bind())

    for kube in session.query(Kube).all():
        kube.disk_space /= 2 ** 20

    session.commit()


def downgrade():
    session = sa.orm.sessionmaker()(bind=op.get_bind())

    for kube in session.query(Kube).all():
        kube.disk_space *= 2 ** 20

    session.commit()

    op.drop_column('kubes', 'disk_space_units')
