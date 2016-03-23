from functools import wraps
from flask import current_app
from rbac.acl import Registry as RegistryOrigin
from rbac.context import IdentityContext

from .models import Resource, Role
from ..core import cache
from ..utils import PermissionDenied, get_user_role


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


class check_permission(object):
    """Improved version of check_permission.

    Original function raises assertion error if resource was not found, but this
    one will throw warning and deny access.
    Also, this varsion uses exception inherited from APIError.

    As an original method, this one could be used as a decorator, a context
    manager, a boolean-like value or directly by calling method check().
    """

    def __init__(self, operation, resource, **exception_kwargs):
        self.operation = operation
        self.resource = resource
        self.exception_kwargs = exception_kwargs
        self.exception_kwargs.setdefault('exception', PermissionDenied)
        self.checker = rbac_context.check_permission(self.operation, self.resource,
                                                     **self.exception_kwargs)

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wraps(func)(wrapper)

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def __nonzero__(self):
        return not self.undefined_resource_warning() and bool(self.checker)

    def undefined_resource_warning(self):
        if self.resource not in acl._resources:
            current_app.logger.warn("RBAC: undefined resource '{0}'".format(
                                    self.resource))
            return True

    def check(self):
        if self.undefined_resource_warning():
            raise PermissionDenied()
        return self.checker.check()


@rbac_context.set_roles_loader
def roles_loader():
    yield get_user_role()


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
