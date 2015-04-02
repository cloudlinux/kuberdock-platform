from functools import wraps
from flask import g, current_app
from flask.ext.login import current_user
from rbac.acl import Registry
from rbac.context import IdentityContext

from ..utils import get_model
from .models import Resource, Role


acl = Registry()
rbac_context = IdentityContext(acl)
# check_permission = rbac_context.check_permission


class check_permission(object):
    def __init__(self, operation, resource, **exception_kwargs):
        self.operation = operation
        self.resource = resource
        self.exception_kwargs = exception_kwargs

    def __call__(self, m):
        @wraps(m)
        def _call_(*args, **kwargs):
            if self.resource not in acl._resources:
                current_app.logger.error(
                    "RBAC failed: undefined resource '{0}'".format(
                        self.resource))
                return m(*args, **kwargs)
            return rbac_context.check_permission(
                self.operation, self.resource, **self.exception_kwargs)(m)(
                    *args, **kwargs)
        return _call_


def init_permissions():
    if get_model('rbac_resource') is None or get_model('rbac_role') is None:
        return
    resources = {}
    for res in Resource.all():
        acl.add_resource(res.name)
        resources[res.id] = res
    for r in Role.all():
        role = RoleWrapper(r.rolename)
        for perm, res, allow in r.perms():
            if allow:
                role.allow(perm, res)
            else:
                role.deny(perm, res)


@rbac_context.set_roles_loader
def roles_loader():
    yield get_user_role()


# separate function because set_roles_loader decorator don't return function. Lib bug.
def get_user_role():
    try:
        return current_user.role.rolename
    except AttributeError:
        try:
            return g.user.role.rolename
        except AttributeError:
            return 'AnonymousUser'


class RoleWrapper(object):
    """
    It's just a wrapper to minimize typo errors
    """
    def __init__(self, rolename, parents=[]):
        self.rolename = rolename
        acl.add_role(rolename, [x.rolename for x in parents])

    def allow(self, action, resource):
        acl.allow(self.rolename, action, resource)
        if (self.rolename, action, resource) in acl._denied:
            del acl._denied[self.rolename, action, resource]

    def deny(self, action, resource):
        acl.deny(self.rolename, action, resource)
        if (self.rolename, action, resource) in acl._allowed:
            del acl._allowed[self.rolename, action, resource]


import rbac_rules   # load after acl end RoleWrapper definition


def gen_roles():    # only after load rbac_rules
    for role in acl._roles:
        if role == 'AnonymousUser':
            continue
        yield role