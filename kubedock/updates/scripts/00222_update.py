
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

from kubedock.rbac.models import Resource, Permission, Role


def upgrade(upd, with_testing, *args, **kwargs):
    resource = Resource.query.filter(
        Resource.name == 'predefined_apps').first()
    roles_ids = [role.id for role in Role.filter(Role.rolename != 'Admin')]
    admin_role = Role.filter_by(rolename='Admin').first()

    Permission(
        resource_id=resource.id,
        name='get_unavailable',
        role_id=admin_role.id,
        allow=True
    ).save()

    for role_id in roles_ids:
        Permission(
            resource_id=resource.id,
            name='get_unavailable',
            role_id=role_id,
            allow=False
        ).save()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    resource = Resource.query.filter(
        Resource.name == 'predefined_apps').first()

    Permission.query.filter_by(name='get_unavailable',
                               resource_id=resource.id)\
        .delete(synchronize_session='fetch')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass