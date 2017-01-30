
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

from kubedock.core import db
from kubedock.rbac.models import Permission, Role, Resource


def _set_permission(value):
    resources = db.session.query(Resource.id).filter(
        Resource.name == 'ippool').subquery()
    roles = db.session.query(Role.id).filter(
        Role.rolename.in_(('User', 'TrialUser'))).subquery()
    Permission.query.filter(
        Permission.name.in_(('get', 'view')),
        # there are some problems with join in update, use subquery instead
        Permission.resource_id.in_(resources),
        Permission.role_id.in_(roles)
    ).update({Permission.allow: value}, synchronize_session=False)
    db.session.commit()


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Forbid user to see ip pool...')
    _set_permission(False)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Allow user to see ip pool...')
    _set_permission(True)
