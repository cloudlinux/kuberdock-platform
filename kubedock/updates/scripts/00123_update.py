
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

from kubedock.rbac.fixtures import (
    Role, Permission, Resource, add_permissions,
    add_roles, _add_permissions, permissions_base,
)
from kubedock.users.models import User, db


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Removing HostingPanel role and user...')
    user_role = Role.query.filter(Role.rolename == 'User').first()
    User.query.filter(User.username == 'hostingPanel').update(
        {User.role_id: user_role.id, User.deleted: True})
    Permission.query.delete()
    Resource.query.delete()
    Role.query.filter(Role.rolename == 'HostingPanel').delete()
    add_permissions()
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Creating HostingPanel role and user...')
    add_roles([('HostingPanel', True)])
    role = Role.filter_by(rolename='HostingPanel').first()
    user = User.filter_by(username='hostingPanel').first()
    if not user:
        db.session.add(User(username='hostingPanel', role=role,
                            password='hostingPanel', active=True))
    else:
        user.deleted = False
        user.role_id = role.id
    perms = dict(permissions_base, **{
        ('images', 'get'): True,
        ('images', 'isalive'): True,
        ('predefined_apps', 'get'): True,
    })
    _add_permissions([(resource, role.rolename, action, allow)
                      for (resource, action), allow in perms.iteritems()])
    db.session.commit()
