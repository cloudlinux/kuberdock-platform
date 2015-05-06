from .models import Resource, Role, Permission


RESOURCES = ("users", "nodes", "pods", "ippool", "static_pages", 
             "notifications")

ROLES = (
    "Admin",
    "User",
    "TrialUser"
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
    ("pods", "Admin", "create", True),
    ("pods", "Admin", "get", True),
    ("pods", "Admin", "edit", True),
    ("pods", "Admin", "delete", True),
    ("ippool", "Admin", "create", True),
    ("ippool", "Admin", "get", True),
    ("ippool", "Admin", "edit", True),
    ("ippool", "Admin", "delete", True),
    ("ippool", "Admin", "view", True),
    ("static_pages", "Admin", "create", True),
    ("static_pages", "Admin", "get", True),
    ("static_pages", "Admin", "edit", True),
    ("static_pages", "Admin", "delete", True),
    ("static_pages", "Admin", "view", True),
    ("notifications", "Admin", "create", True),
    ("notifications", "Admin", "get", True),
    ("notifications", "Admin", "edit", True),
    ("notifications", "Admin", "delete", True),
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
    ("ippool", "User", "get", True),
    ("ippool", "User", "edit", False),
    ("ippool", "User", "delete", False),
    ("ippool", "User", "view", True),
    ("static_pages", "User", "create", False),
    ("static_pages", "User", "get", False),
    ("static_pages", "User", "edit", False),
    ("static_pages", "User", "delete", False),
    ("static_pages", "User", "view", True),
    ("notifications", "User", "create", False),
    ("notifications", "User", "get", False),
    ("notifications", "User", "edit", False),
    ("notifications", "User", "delete", False),
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
    ("pods", "TrialUser", "create", False),
    ("pods", "TrialUser", "get", True),
    ("pods", "TrialUser", "edit", True),
    ("pods", "TrialUser", "delete", True),
    ("ippool", "TrialUser", "create", False),
    ("ippool", "TrialUser", "get", True),
    ("ippool", "TrialUser", "edit", False),
    ("ippool", "TrialUser", "delete", False),
    ("ippool", "TrialUser", "view", True),
    ("static_pages", "TrialUser", "create", False),
    ("static_pages", "TrialUser", "get", False),
    ("static_pages", "TrialUser", "edit", False),
    ("static_pages", "TrialUser", "delete", False),
    ("static_pages", "TrialUser", "view", True),
    ("notifications", "TrialUser", "create", False),
    ("notifications", "TrialUser", "get", False),
    ("notifications", "TrialUser", "edit", False),
    ("notifications", "TrialUser", "delete", False),

)


def add_permissions():
    # Add resources
    resources = {}
    roles = {}
    for r in RESOURCES:
        res = Resource.create(name=r)
        res.save()
        resources[r] = res
    # Add roles
    for r in ROLES:
        role = Role.create(rolename=r)
        role.save()
        roles[r] = role
    # Add permissions
    for res, role, perm, allow in PERMISSIONS:
        p = Permission.create(resource_id=resources[res].id,
                              role_id=roles[role].id, name=perm, allow=allow)
        p.save()


if __name__ == '__main__':
    add_permissions()