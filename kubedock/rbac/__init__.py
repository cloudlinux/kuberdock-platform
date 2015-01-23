from flask.ext.login import current_user
from rbac.acl import Registry
from rbac.context import IdentityContext

acl = Registry()
rbac_context = IdentityContext(acl)
check_permission = rbac_context.check_permission


@rbac_context.set_roles_loader
def roles_loader():
    yield current_user.role.rolename


class RoleWrapper(object):
    """
    It's just a wrapper to minimize typo errors
    """
    def __init__(self, rolename, parents=[]):
        self.rolename = rolename
        acl.add_role(rolename, [x.rolename for x in parents])

    def allow(self, action, resource):
        acl.allow(self.rolename, action, resource)

    def deny(self, action, resource):
        acl.deny(self.rolename, action, resource)


import rbac_rules   # load after acl end RoleWrapper definition


def gen_roles():    # only after load rbac_rules
    for role in acl._roles:
        yield role