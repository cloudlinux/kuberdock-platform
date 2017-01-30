
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

from kubedock.updates import helpers
from kubedock.static_pages.models import MenuItemRole, MenuItem
from kubedock.rbac.models import Role, Resource, Permission


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add MenuItemRole model.')
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='241a7b04a9ff')
    admin = Role.filter(Role.rolename == 'Admin').first()
    trialuser = Role.filter(Role.rolename == 'TrialUser').first()
    user = Role.filter(Role.rolename == 'User').first()
    menu_pods = MenuItem.filter(MenuItem.name == 'Pods').first()
    menu_publicip = MenuItem.filter(MenuItem.name == 'Public IPs').first()
    menu_pv = MenuItem.filter(MenuItem.name == 'Persistent volumes').first()
    menu_nodes = MenuItem.filter(MenuItem.name == 'Nodes').first()
    menu_papps = MenuItem.filter(
        MenuItem.name == 'Predefined Applications').first()
    menu_settings = MenuItem.filter(MenuItem.name == 'Settings').first()
    menu_adm = MenuItem.filter(MenuItem.name == 'Administration').first()
    menu_users = MenuItem.filter(MenuItem.name == 'Users').first()
    menu_ippool = MenuItem.filter(MenuItem.name == 'IP pool').first()
    MenuItemRole.create(menuitem=menu_pods, role=user)
    MenuItemRole.create(menuitem=menu_pods, role=trialuser)
    MenuItemRole.create(menuitem=menu_publicip, role=user)
    MenuItemRole.create(menuitem=menu_publicip, role=trialuser)
    MenuItemRole.create(menuitem=menu_pv, role=user)
    MenuItemRole.create(menuitem=menu_pv, role=trialuser)
    MenuItemRole.create(menuitem=menu_nodes, role=admin)
    MenuItemRole.create(menuitem=menu_papps, role=admin)
    MenuItemRole.create(menuitem=menu_settings, role=admin)
    MenuItemRole.create(menuitem=menu_settings, role=user)
    MenuItemRole.create(menuitem=menu_settings, role=trialuser)
    MenuItemRole.create(menuitem=menu_adm, role=admin)
    MenuItemRole.create(menuitem=menu_users, role=admin)
    MenuItemRole.create(menuitem=menu_ippool, role=admin)

    resource = Resource.filter(Resource.name == 'static_pages').first()
    if resource:
        Permission.filter(Permission.resource == resource).delete()
        resource.delete()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
