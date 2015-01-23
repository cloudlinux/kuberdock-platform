from . import acl
from . import RoleWrapper as Role

"""
Action it's just a human-friendly string that identifies what we want to do with resource
To add new one:
 1. Add it to any appropriate role, like: RoleName.allow("new_action", "existing_resource")
 2. Place check_permission('new_action', 'existing_resource') at right place in code
"""

"""
RESOURCES it's just a strings, nothing special.
They also can have parend-child hierarchy.

To add new:
 1. Add it here (and choose parent resources)
 2. Allow all actions on it to SuperAdmin role
 3. Set check_permission('action', 'resource') at right place in code
 4. Allow/deny actions on it to roles
"""
acl.add_resource("users")
acl.add_resource("minions")
acl.add_resource("pods", ["minions"])   # TODO test inheritance

"""
ROLES it's just a strings, wrapped in a class to minimize syntax errors and for convenience.
They also can have parend-child hierarchy.

To add new role:
 1. add it here (and choose parent roles), like:
    RoleName = Role("RoleName")
    # permissions:
    RoleName.allow("action", "some_existing_resource")
    RoleName.deny("other_action", "some_existing_resource")
    ...
 2. createdb.py to insert all this roles to db
"""
SuperAdmin = Role("SuperAdmin")
SuperAdmin.allow("create", "users")
SuperAdmin.allow("get", "users")
SuperAdmin.allow("edit", "users")
SuperAdmin.allow("delete", "users")

SuperAdmin.allow("create", "minions")
SuperAdmin.allow("get", "minions")
SuperAdmin.allow("edit", "minions")
SuperAdmin.allow("delete", "minions")

SuperAdmin.allow("create", "pods")
SuperAdmin.allow("get", "pods")
SuperAdmin.allow("edit", "pods")
SuperAdmin.allow("delete", "pods")


Admin = Role('Admin', [SuperAdmin])
Admin.deny("delete", "users")
Admin.deny("delete", "minions")
Admin.deny("delete", "pods")


User = Role('User')
User.allow("create", "pods")
User.allow("get", "pods")
User.allow("edit", "pods")
User.allow("delete", "pods")


TrialUser = Role('TrialUser', [User])
TrialUser.deny("create", "pods")