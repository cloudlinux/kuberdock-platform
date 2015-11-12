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
