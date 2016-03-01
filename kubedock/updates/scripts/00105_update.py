from kubedock.core import db
from kubedock.users.models import User
from kubedock.rbac.models import Role
from kubedock.rbac import fixtures
from kubedock.static_pages.models import MenuItemRole

PERMISSIONS = (
    # Admin
    ("yaml_pods", "Admin", "create", False),
    # User
    ("yaml_pods", "User", "create", True),
    # LimitedUser
    ("users", "LimitedUser", "create", False),
    ("users", "LimitedUser", "get", False),
    ("users", "LimitedUser", "edit", False),
    ("users", "LimitedUser", "delete", False),
    ("users", "LimitedUser", "auth_by_another", False),
    ("nodes", "LimitedUser", "create", False),
    ("nodes", "LimitedUser", "get", False),
    ("nodes", "LimitedUser", "edit", False),
    ("nodes", "LimitedUser", "delete", False),
    ("nodes", "LimitedUser", "redeploy", False),
    ("pods", "LimitedUser", "create", False),
    ("pods", "LimitedUser", "get", True),
    ("pods", "LimitedUser", "edit", True),
    ("pods", "LimitedUser", "delete", True),
    ("yaml_pods", "LimitedUser", "create", True),
    ("ippool", "LimitedUser", "create", False),
    ("ippool", "LimitedUser", "get", False),
    ("ippool", "LimitedUser", "edit", False),
    ("ippool", "LimitedUser", "delete", False),
    ("ippool", "LimitedUser", "view", False),
    ("notifications", "LimitedUser", "create", False),
    ("notifications", "LimitedUser", "get", False),
    ("notifications", "LimitedUser", "edit", False),
    ("notifications", "LimitedUser", "delete", False),
    ("images", "LimitedUser", "get", True),
    ("images", "LimitedUser", "isalive", True),
    ("predefined_apps", "LimitedUser", "create", False),
    ("predefined_apps", "LimitedUser", "get", True),
    ("predefined_apps", "LimitedUser", "edit", False),
    ("predefined_apps", "LimitedUser", "delete", False),
    # TrialUser
    ("yaml_pods", "TrialUser", "create", True),
    # HostingPanel
    ("yaml_pods", "HostingPanel", "create", False),
)

RESOURCES = ("yaml_pods",)

ROLES = (
    ("LimitedUser", False),
)


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add roles {}, resources {} and its permissions...'.format(
        ROLES, RESOURCES))
    fixtures.add_permissions(
        roles=ROLES, resources=RESOURCES, permissions=PERMISSIONS)
    upd.print_log('Add MenuRoles...')
    PAUserRole = Role.query.filter(Role.rolename == 'LimitedUser').first()
    for menu_role in Role.query.filter(Role.rolename == 'User').first().menus_assocs:
        db.session.add(MenuItemRole(role=PAUserRole, menuitem_id=menu_role.menuitem_id))
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Remove MenuRoles...')
    PAUserRole = Role.query.filter(Role.rolename == 'LimitedUser').first()
    if PAUserRole is not None:
        for menu_role in PAUserRole.menus_assocs:
            db.session.delete(menu_role)

    upd.print_log('Delete roles {} with its permissions...'.format(ROLES))
    fixtures.delete_roles([name for name, internal in ROLES])
    upd.print_log(
        'Delete resources {} with its permissions...'.format(RESOURCES))
    fixtures.delete_resources(RESOURCES)
    db.session.commit()
