
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
from kubedock.users.models import User
from kubedock.rbac.models import Role
from kubedock.rbac import fixtures

PERMISSIONS = (
    # Admin
    ("images", "Admin", "get", True),
    ("images", "Admin", "isalive", True),
    ("predefined_apps", "Admin", "create", True),
    ("predefined_apps", "Admin", "get", True),
    ("predefined_apps", "Admin", "edit", True),
    ("predefined_apps", "Admin", "delete", True),
    # User
    ("images", "User", "get", True),
    ("images", "User", "isalive", True),
    ("predefined_apps", "User", "create", False),
    ("predefined_apps", "User", "get", True),
    ("predefined_apps", "User", "edit", False),
    ("predefined_apps", "User", "delete", False),
    # TrialUser
    ("images", "TrialUser", "get", True),
    ("images", "TrialUser", "isalive", True),
    ("predefined_apps", "TrialUser", "create", False),
    ("predefined_apps", "TrialUser", "get", True),
    ("predefined_apps", "TrialUser", "edit", False),
    ("predefined_apps", "TrialUser", "delete", False),
    # HostingPanel
    ("users", "HostingPanel", "create", False),
    ("users", "HostingPanel", "get", False),
    ("users", "HostingPanel", "edit", False),
    ("users", "HostingPanel", "delete", False),
    ("users", "HostingPanel", "auth_by_another", False),
    ("nodes", "HostingPanel", "create", False),
    ("nodes", "HostingPanel", "get", False),
    ("nodes", "HostingPanel", "edit", False),
    ("nodes", "HostingPanel", "delete", False),
    ("nodes", "HostingPanel", "redeploy", False),
    ("pods", "HostingPanel", "create", False),
    ("pods", "HostingPanel", "get", False),
    ("pods", "HostingPanel", "edit", False),
    ("pods", "HostingPanel", "delete", False),
    ("ippool", "HostingPanel", "create", False),
    ("ippool", "HostingPanel", "get", False),
    ("ippool", "HostingPanel", "edit", False),
    ("ippool", "HostingPanel", "delete", False),
    ("ippool", "HostingPanel", "view", False),
    ("static_pages", "HostingPanel", "create", False),
    ("static_pages", "HostingPanel", "get", False),
    ("static_pages", "HostingPanel", "edit", False),
    ("static_pages", "HostingPanel", "delete", False),
    ("static_pages", "HostingPanel", "view", False),
    ("notifications", "HostingPanel", "create", False),
    ("notifications", "HostingPanel", "get", False),
    ("notifications", "HostingPanel", "edit", False),
    ("notifications", "HostingPanel", "delete", False),
    ("images", "HostingPanel", "get", True),
    ("images", "HostingPanel", "isalive", True),
    ("predefined_apps", "HostingPanel", "create", False),
    ("predefined_apps", "HostingPanel", "get", True),
    ("predefined_apps", "HostingPanel", "edit", False),
    ("predefined_apps", "HostingPanel", "delete", False),

)

RESOURCES = ("images", "predefined_apps")

ROLES = (
    ("HostingPanel", True),
)

USER = "hostingPanel"


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add roles {}, resources {} and its permissions...'.format(
        ROLES, RESOURCES))
    fixtures.add_permissions(
        roles=ROLES, resources=RESOURCES, permissions=PERMISSIONS)
    upd.print_log('Add {} user...'.format(USER))
    u = db.session.query(User).filter(User.username == USER).first()
    if not u:
        r = Role.filter_by(rolename='HostingPanel').first()
        u = User.create(username=USER, password=USER, role=r, active=True)
        u.save()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Delete roles {} with its permissions...'.format(ROLES))
    fixtures.delete_roles(ROLES)
    upd.print_log(
        'Delete resources {} with its permissions...'.format(RESOURCES))
    fixtures.delete_resources(RESOURCES)
    upd.print_log('Delete user {}...'.format(USER))
    db.session.query(User).filter(User.username == USER).delete()
    db.session.commit()
