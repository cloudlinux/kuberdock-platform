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
    # PredefinedAppUser
    ("users", "PredefinedAppUser", "create", False),
    ("users", "PredefinedAppUser", "get", False),
    ("users", "PredefinedAppUser", "edit", False),
    ("users", "PredefinedAppUser", "delete", False),
    ("users", "PredefinedAppUser", "auth_by_another", False),
    ("nodes", "PredefinedAppUser", "create", False),
    ("nodes", "PredefinedAppUser", "get", False),
    ("nodes", "PredefinedAppUser", "edit", False),
    ("nodes", "PredefinedAppUser", "delete", False),
    ("nodes", "PredefinedAppUser", "redeploy", False),
    ("pods", "PredefinedAppUser", "create", False),
    ("pods", "PredefinedAppUser", "get", True),
    ("pods", "PredefinedAppUser", "edit", True),
    ("pods", "PredefinedAppUser", "delete", True),
    ("yaml_pods", "PredefinedAppUser", "create", True),
    ("ippool", "PredefinedAppUser", "create", False),
    ("ippool", "PredefinedAppUser", "get", False),
    ("ippool", "PredefinedAppUser", "edit", False),
    ("ippool", "PredefinedAppUser", "delete", False),
    ("ippool", "PredefinedAppUser", "view", False),
    ("notifications", "PredefinedAppUser", "create", False),
    ("notifications", "PredefinedAppUser", "get", False),
    ("notifications", "PredefinedAppUser", "edit", False),
    ("notifications", "PredefinedAppUser", "delete", False),
    ("images", "PredefinedAppUser", "get", True),
    ("images", "PredefinedAppUser", "isalive", True),
    ("predefined_apps", "PredefinedAppUser", "create", False),
    ("predefined_apps", "PredefinedAppUser", "get", True),
    ("predefined_apps", "PredefinedAppUser", "edit", False),
    ("predefined_apps", "PredefinedAppUser", "delete", False),
    # TrialUser
    ("yaml_pods", "TrialUser", "create", True),
    # HostingPanel
    ("yaml_pods", "HostingPanel", "create", False),
)

RESOURCES = ("yaml_pods")

ROLES = (
    ("PredefinedAppUser", False),
)


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add roles {}, resources {} and its permissions...'.format(
        ROLES, RESOURCES))
    fixtures.add_permissions(
        roles=ROLES, resources=RESOURCES, permissions=PERMISSIONS)
    upd.print_log('Add MenuRoles...')
    PAUserRole = Role.query.filter(Role.rolename == 'PredefinedAppUser').first()
    for menu_role in Role.query.filter(Role.rolename == 'User').first().menus_assocs:
        db.session.add(MenuItemRole(role=PAUserRole, menuitem_id=menu_role.menuitem_id))
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Remove MenuRoles...')
    PAUserRole = Role.query.filter(Role.rolename == 'PredefinedAppUser').first()
    if PAUserRole is not None:
        for menu_role in PAUserRole.menus_assocs:
            db.session.delete(menu_role)

    upd.print_log('Delete roles {} with its permissions...'.format(ROLES))
    fixtures.delete_roles([name for name, internal in ROLES])
    upd.print_log(
        'Delete resources {} with its permissions...'.format(RESOURCES))
    fixtures.delete_resources(RESOURCES)
    db.session.commit()
