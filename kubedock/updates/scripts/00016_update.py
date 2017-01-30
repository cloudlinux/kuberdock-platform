
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

from kubedock.rbac.models import Permission, Resource, Role


def _set_new(val):
    role = Role.filter_by(rolename='Admin').first()
    pod_res = Resource.filter_by(name='pods').first()
    perms = Permission.filter_by(role_id=role.id, resource_id=pod_res.id).all()
    for perm in perms:
        if val:
            perm.set_allow()
        else:
            perm.set_deny()


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log("Disable admin's pods permissions")
    _set_new(False)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log("Reenable admin's pods permissions")
    _set_new(True)
