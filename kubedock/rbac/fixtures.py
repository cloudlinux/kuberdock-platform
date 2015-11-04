from kubedock.core import db
from .models import Resource, Role, Permission


RESOURCES = ("users", "nodes", "pods", "ippool",
             "notifications", "system_settings", "images", "predefined_apps")

ROLES = (
    ("Admin", False),
    ("User", False),
    ("TrialUser", False),
    ("HostingPanel", True),
)

PERMISSIONS = (
    # Admin
    ("users", "Admin", "create", True),
    ("users", "Admin", "get", True),
    ("users", "Admin", "edit", True),
    ("users", "Admin", "delete", True),
    ("users", "Admin", "auth_by_another", True),
    ("nodes", "Admin", "create", True),
    ("nodes", "Admin", "get", True),
    ("nodes", "Admin", "edit", True),
    ("nodes", "Admin", "delete", True),
    ("nodes", "Admin", "redeploy", True),
    ("pods", "Admin", "create", False),
    ("pods", "Admin", "get", False),
    ("pods", "Admin", "edit", False),
    ("pods", "Admin", "delete", False),
    ("ippool", "Admin", "create", True),
    ("ippool", "Admin", "get", True),
    ("ippool", "Admin", "edit", True),
    ("ippool", "Admin", "delete", True),
    ("ippool", "Admin", "view", True),
    ("notifications", "Admin", "create", True),
    ("notifications", "Admin", "get", True),
    ("notifications", "Admin", "edit", True),
    ("notifications", "Admin", "delete", True),
    ("system_settings", "Admin", "read", True),
    ("system_settings", "Admin", "write", True),
    ("system_settings", "Admin", "delete", True),
    ("images", "Admin", "get", True),
    ("images", "Admin", "isalive", True),
    ("predefined_apps", "Admin", "create", True),
    ("predefined_apps", "Admin", "get", True),
    ("predefined_apps", "Admin", "edit", True),
    ("predefined_apps", "Admin", "delete", True),
    # User
    ("users", "User", "create", False),
    ("users", "User", "get", False),
    ("users", "User", "edit", False),
    ("users", "User", "delete", False),
    ("users", "User", "auth_by_another", False),
    ("nodes", "User", "create", False),
    ("nodes", "User", "get", False),
    ("nodes", "User", "edit", False),
    ("nodes", "User", "delete", False),
    ("nodes", "User", "redeploy", False),
    ("pods", "User", "create", True),
    ("pods", "User", "get", True),
    ("pods", "User", "edit", True),
    ("pods", "User", "delete", True),
    ("ippool", "User", "create", False),
    ("ippool", "User", "get", False),
    ("ippool", "User", "edit", False),
    ("ippool", "User", "delete", False),
    ("ippool", "User", "view", False),
    ("notifications", "User", "create", False),
    ("notifications", "User", "get", False),
    ("notifications", "User", "edit", False),
    ("notifications", "User", "delete", False),
    ("images", "User", "get", True),
    ("images", "User", "isalive", True),
    ("predefined_apps", "User", "create", False),
    ("predefined_apps", "User", "get", True),
    ("predefined_apps", "User", "edit", False),
    ("predefined_apps", "User", "delete", False),
    # TrialUser
    ("users", "TrialUser", "create", False),
    ("users", "TrialUser", "get", False),
    ("users", "TrialUser", "edit", False),
    ("users", "TrialUser", "delete", False),
    ("users", "TrialUser", "auth_by_another", False),
    ("nodes", "TrialUser", "create", False),
    ("nodes", "TrialUser", "get", False),
    ("nodes", "TrialUser", "edit", False),
    ("nodes", "TrialUser", "delete", False),
    ("nodes", "TrialUser", "redeploy", False),
    ("pods", "TrialUser", "create", True),
    ("pods", "TrialUser", "get", True),
    ("pods", "TrialUser", "edit", True),
    ("pods", "TrialUser", "delete", True),
    ("ippool", "TrialUser", "create", False),
    ("ippool", "TrialUser", "get", False),
    ("ippool", "TrialUser", "edit", False),
    ("ippool", "TrialUser", "delete", False),
    ("ippool", "TrialUser", "view", False),
    ("notifications", "TrialUser", "create", False),
    ("notifications", "TrialUser", "get", False),
    ("notifications", "TrialUser", "edit", False),
    ("notifications", "TrialUser", "delete", False),
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


def add_roles(roles=()):
    for r in roles:
        if not Role.filter(Role.rolename == r[0]).first():
            role = Role.create(rolename=r[0], internal=r[1])
            role.save()


def delete_roles(roles=()):
    """ Delete roles with its permissions
    """
    for role_name in roles:
        role = Role.filter(Role.rolename == role_name).first()
        if role:
            Permission.filter(Permission.role == role).delete()
            db.session.commit()
            role.delete()


def add_resources(resources=()):
    for res in resources:
        if not Resource.filter(Resource.name == res).first():
            resource = Resource.create(name=res)
            resource.save()


def delete_resources(resources=()):
    """ Delete resources with its permissions
    """
    for resource_name in resources:
        resource = Resource.filter(Resource.name == resource_name).first()
        if resource:
            Permission.filter(Permission.resource == resource).delete()
            db.session.commit()
            resource.delete()


def _add_permissions(permissions=()):
    for res, role, perm, allow in permissions:
        resource = Resource.query.filter_by(name=res).first()
        role = Role.query.filter_by(rolename=role).first()
        if role and resource:
            exist = Permission.filter(Permission.role == role). \
                filter(Permission.resource == resource). \
                filter(Permission.allow == allow). \
                filter(Permission.name == perm).first()
            if not exist:
                permission = Permission.create(
                    resource_id=resource.id,
                    role_id=role.id, name=perm, allow=allow)
                permission.save()


def add_permissions(roles=None, resources=None, permissions=None):
    if not roles:
        roles = ROLES
    if not resources:
        resources = RESOURCES
    if not permissions:
        permissions = PERMISSIONS
    add_roles(roles)
    add_resources(resources)
    _add_permissions(permissions)


if __name__ == '__main__':
    add_permissions()
