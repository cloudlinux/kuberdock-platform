
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

from copy import deepcopy
from .models import Menu, MenuItem, MenuItemRole
from kubedock.rbac.models import Role


def get_menus(aws=False):
    return [
        dict(
            region=Menu.REGION_NAVBAR,
            name='Navbar menu',
            items=[
                dict(name="Pods", path="#pods", ordering=0,
                     roles=["User", "TrialUser", "LimitedUser"]),
                dict(name="Access endpoints" if aws else "Public IPs",
                     path="#publicIPs", ordering=1,
                     roles=["User", "TrialUser", "LimitedUser"]),
                dict(name="Persistent volumes", path="#persistent-volumes",
                     ordering=2, roles=["User", "TrialUser", "LimitedUser"]),
                dict(name="Nodes", path="#nodes", ordering=1, roles=["Admin"]),
                dict(name="Predefined Applications", path="#predefined-apps",
                     ordering=2, roles=["Admin"]),
                dict(name="Settings", path="#settings", ordering=4,
                     roles=["Admin"]),
                dict(
                    name="Administration",
                    ordering=5,
                    children=[
                        dict(name="Users", path="#users", ordering=0,
                             roles=["Admin"]),
                        dict(name="Access endpoints" if aws else "IP pool",
                             path="#ippool", ordering=1, roles=["Admin"]),
                        dict(name="Domains control", path="#domains", ordering=2,
                             roles=["Admin"]),
                    ],
                    roles=["Admin"]
                ),
            ]
        ),
    ]


def generate_menu(aws=False):

    def add_menu_items(items, menu, parent=None,):
        for item in items:
            roles = item.pop('roles', [])
            children = item.pop('children', None)
            menu_item = MenuItem(**item)
            menu_item.menu = menu
            menu_item.parent = parent
            menu_item.save()
            for rolename in roles:
                role = Role.filter(Role.rolename == rolename).one()
                item_role = MenuItemRole(role=role, menuitem=menu_item)
                item_role.save()
            if children:
                add_menu_items(children, menu, parent=menu_item)

    menus = deepcopy(get_menus(aws))
    for menu in menus:
        items = menu.pop('items')
        menu = Menu.create(**menu)
        menu.save()
        add_menu_items(items, menu)


if __name__ == '__main__':
    # Generate menus, menu items
    generate_menu()
