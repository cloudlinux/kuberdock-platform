
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

import json
from kubedock.static_pages.models import MenuItem, MenuItemRole
from kubedock.rbac.models import Role


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add menus Persistent volumes and Public IPs')
    user = Role.filter(Role.rolename == "User").one()
    trial_user = Role.filter(Role.rolename == "TrialUser").one()
    public_ips = MenuItem.create(name="Public IPs", path="/publicIPs/",
                                 ordering=1, menu_id=1)
    public_ips.save()
    perm = MenuItemRole(role=user, menuitem=public_ips)
    perm = MenuItemRole(role=trial_user, menuitem=public_ips)
    perm.save()
    p = MenuItem.create(name="Persistent volumes", path="/persistent-volumes/",
                        ordering=2, menu_id=1)
    p.save()
    perm = MenuItemRole(role=user, menuitem=p)
    perm = MenuItemRole(role=trial_user, menuitem=p)
    perm.save()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Delete menus Persistent volumes and Public IPs')
    ps = MenuItem.filter(MenuItem.name == 'Persistent volumes').first()
    if ps:
        MenuItemRole.filter(MenuItemRole.menuitem == ps).delete()
        ps.delete()
    pip = MenuItem.filter(MenuItem.name == 'Public IPs').first()
    if pip:
        MenuItemRole.filter(MenuItemRole.menuitem == pip).delete()
        pip.delete()
