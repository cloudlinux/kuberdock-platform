from functools import wraps
from flask import g, current_app
from flask.ext.login import current_user, logout_user
from rbac.acl import Registry as RegistryOrigin
from rbac.context import IdentityContext

from .models import Resource, Role
from ..core import cache


class Registry(RegistryOrigin):
    @property
    def _get_roles(self):
        return cache.get('roles') or {}

    @property
    def _get_resources(self):
        return cache.get('resources') or {}

    @property
    def _get_allowed(self):
        return cache.get('allowed') or {}

    @property
    def _get_denied(self):
        return cache.get('denied') or {}

    def _set_registry(self, key, value):
        cache.set(key, value)
        setattr(self, '_{0}'.format(key), getattr(self, '_get_{0}'.format(key)))

    def init_permissions(self):
        resources = {}
        for res in Resource.all():
            resources[res.name] = set()
        roles = {}
        allowed = {}
        denied = {}
        for r in Role.all():
            roles[r.rolename] = set()
            for perm, res, allow in r.perms():
                roles[r.rolename, perm, res] = None
                if allow:
                    allowed[r.rolename, perm, res] = None
                else:
                    denied[r.rolename, perm, res] = None
        self._set_registry('roles', roles)
        self._set_registry('resources', resources)
        self._set_registry('allowed', allowed)
        self._set_registry('denied', denied)


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
                # current_app.logger.error(
                #     "RBAC failed: undefined resource '{0}'".format(
                #         self.resource))
                return m(*args, **kwargs)
            return rbac_context.check_permission(
                self.operation, self.resource, **self.exception_kwargs)(m)(
                    *args, **kwargs)
        return _call_


@rbac_context.set_roles_loader
def roles_loader():
    yield get_user_role()


# separate function because set_roles_loader decorator don't return function. Lib bug.
def get_user_role():
    rolename = 'AnonymousUser'
    try:
        rolename = current_user.role.rolename
    except AttributeError:
        try:
            rolename = g.user.role.rolename
        except AttributeError:
            pass
    if rolename == 'AnonymousUser':
        logout_user()
    return rolename


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