from .models import Resource, Role, Permission


RESOURCES = ("users", "nodes", "pods", "ippool", "static_pages", 
             "notifications")

ROLES = ("SuperAdmin", "Administrator", "User", "TrialUser")

PERMISSIONS = (
    # SuperAdmin
    ("users", "SuperAdmin", "create", True),
    ("users", "SuperAdmin", "get", True),
    ("users", "SuperAdmin", "edit", True),
    ("users", "SuperAdmin", "delete", True),
    ("users", "SuperAdmin", "auth_by_another", True),
    ("nodes", "SuperAdmin", "create", True),
    ("nodes", "SuperAdmin", "get", True),
    ("nodes", "SuperAdmin", "edit", True),
    ("nodes", "SuperAdmin", "delete", True),
    ("pods", "SuperAdmin", "create", True),
    ("pods", "SuperAdmin", "get", True),
    ("pods", "SuperAdmin", "edit", True),
    ("pods", "SuperAdmin", "delete", True),
    ("ippool", "SuperAdmin", "create", True),
    ("ippool", "SuperAdmin", "get", True),
    ("ippool", "SuperAdmin", "edit", True),
    ("ippool", "SuperAdmin", "delete", True),
    ("ippool", "SuperAdmin", "view", True),
    ("static_pages", "SuperAdmin", "create", True),
    ("static_pages", "SuperAdmin", "get", True),
    ("static_pages", "SuperAdmin", "edit", True),
    ("static_pages", "SuperAdmin", "delete", True),
    ("static_pages", "SuperAdmin", "view", True),
    ("notifications", "SuperAdmin", "create", True),
    ("notifications", "SuperAdmin", "get", True),
    ("notifications", "SuperAdmin", "edit", True),
    ("notifications", "SuperAdmin", "delete", True),
    # Administrator
    ("users", "Administrator", "create", True),
    ("users", "Administrator", "get", True),
    ("users", "Administrator", "edit", True),
    ("users", "Administrator", "delete", True),
    ("users", "Administrator", "auth_by_another", True),
    ("nodes", "Administrator", "create", True),
    ("nodes", "Administrator", "get", True),
    ("nodes", "Administrator", "edit", True),
    ("nodes", "Administrator", "delete", False),
    ("pods", "Administrator", "create", True),
    ("pods", "Administrator", "get", True),
    ("pods", "Administrator", "edit", True),
    ("pods", "Administrator", "delete", False),
    ("ippool", "Administrator", "create", False),
    ("ippool", "Administrator", "get", True),
    ("ippool", "Administrator", "edit", True),
    ("ippool", "Administrator", "delete", False),
    ("ippool", "Administrator", "view", True),
    ("static_pages", "Administrator", "create", True),
    ("static_pages", "Administrator", "get", True),
    ("static_pages", "Administrator", "edit", True),
    ("static_pages", "Administrator", "delete", False),
    ("static_pages", "Administrator", "view", True),
    ("notifications", "Administrator", "create", False),
    ("notifications", "Administrator", "get", True),
    ("notifications", "Administrator", "edit", True),
    ("notifications", "Administrator", "delete", False),
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