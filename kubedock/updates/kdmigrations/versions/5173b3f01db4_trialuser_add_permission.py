
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

Revision ID: 5173b3f01db4
Revises: 3f771e33622a
Create Date: 2015-09-08 11:08:23.914111

"""

# revision identifiers, used by Alembic.
revision = '5173b3f01db4'
down_revision = '3f771e33622a'

from alembic import op
import sqlalchemy as sa


from kubedock.rbac.models import Role, Permission, Resource


def upgrade():
    session = sa.orm.sessionmaker()(bind=op.get_bind())
    permission = session.query(Permission)\
        .join(Role, Role.id == Permission.role_id).join(Resource, Permission.resource_id == Resource.id)\
        .filter(Role.rolename == 'TrialUser').filter(Resource.name == 'pods')\
        .filter(Permission.name == 'create').one()
    permission.allow = True
    session.commit()


def downgrade():
    session = sa.orm.sessionmaker()(bind=op.get_bind())
    permission = session.query(Permission)\
        .join(Role, Role.id == Permission.role_id).join(Resource, Permission.resource_id == Resource.id)\
        .filter(Role.rolename == 'TrialUser').filter(Resource.name == 'pods')\
        .filter(Permission.name == 'create').one()
    permission.allow = False
    session.commit()
