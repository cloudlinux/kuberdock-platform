from kubedock.core import db
from .models import Resource, Role, Permission

ROLES = (
    # rolename, is_internal
    ("Admin", False),
    ("User", False),
    ("LimitedUser", False),
    ("TrialUser", False),
)

resources = {
    'users': ('create', 'get', 'edit', 'delete', 'auth_by_another'),
    'nodes': ('create', 'get', 'edit', 'delete', 'redeploy'),
    'pods': ('own', 'create', 'get', 'edit', 'delete', 'create_non_owned',
             'get_non_owned', 'edit_non_owned', 'delete_non_owned', 'dump'),
    'persistent_volumes': ('own', 'create', 'get', 'edit', 'delete',
                           'create_non_owned', 'get_non_owned',
                           'edit_non_owned', 'delete_non_owned'),
    'yaml_pods': ('create',),
    'ippool': ('create', 'get', 'edit', 'delete', 'view'),
    'notifications': ('create', 'get', 'edit', 'delete'),
    'system_settings': ('read', 'read_private', 'write', 'delete'),
    'images': ('get', 'isalive'),
    'predefined_apps': ('create', 'get', 'edit', 'delete'),
    'pricing': ('create', 'get', 'edit', 'delete', 'get_own'),
    'timezone': ('get',),
    'domains': ('create', 'get', 'edit', 'delete'),
    'allowed-ports': ('get', 'create', 'delete'),
}

permissions_base = {
    (resource, action): False
    for resource, actions in resources.iteritems() for action in actions
    }
permissions = {
    'Admin': dict(permissions_base, **{
        ('users', 'create'): True,
        ('users', 'get'): True,
        ('users', 'edit'): True,
        ('users', 'delete'): True,
        ('users', 'auth_by_another'): True,
        ('nodes', 'create'): True,
        ('nodes', 'get'): True,
        ('nodes', 'edit'): True,
        ('nodes', 'delete'): True,
        ('nodes', 'redeploy'): True,
        ('ippool', 'create'): True,
        ('ippool', 'get'): True,
        ('ippool', 'edit'): True,
        ('ippool', 'delete'): True,
        ('ippool', 'view'): True,
        ('notifications', 'create'): True,
        ('notifications', 'get'): True,
        ('notifications', 'edit'): True,
        ('notifications', 'delete'): True,
        ('system_settings', 'read'): True,
        ('system_settings', 'read_private'): True,
        ('system_settings', 'write'): True,
        ('system_settings', 'delete'): True,
        ('images', 'get'): True,
        ('images', 'isalive'): True,
        ('pods', 'create_non_owned'): True,
        ('pods', 'get_non_owned'): True,
        ('pods', 'edit_non_owned'): True,
        ('pods', 'delete_non_owned'): True,
        ('pods', 'dump'): True,
        ('persistent_volumes', 'create_non_owned'): True,
        ('persistent_volumes', 'get_non_owned'): True,
        ('persistent_volumes', 'edit_non_owned'): True,
        ('persistent_volumes', 'delete_non_owned'): True,
        ('predefined_apps', 'create'): True,
        ('predefined_apps', 'get'): True,
        ('predefined_apps', 'edit'): True,
        ('predefined_apps', 'delete'): True,
        ('pricing', 'get'): True,  # packages, kube types
        ('pricing', 'get_own'): True,
        ('pricing', 'edit'): True,
        ('pricing', 'create'): True,
        ('pricing', 'delete'): True,
        ('timezone', 'get'): True,
        ('domains', 'create'): True,
        ('domains', 'get'): True,
        ('domains', 'edit'): True,
        ('domains', 'delete'): True,
        ('allowed-ports', 'get'): True,
        ('allowed-ports', 'create'): True,
        ('allowed-ports', 'delete'): True,
    }),
    'User': dict(permissions_base, **{
        ('pods', 'own'): True,
        ('pods', 'create'): True,
        ('pods', 'get'): True,
        ('pods', 'edit'): True,
        ('pods', 'delete'): True,
        ('persistent_volumes', 'own'): True,
        ('persistent_volumes', 'create'): True,
        ('persistent_volumes', 'get'): True,
        ('persistent_volumes', 'edit'): True,
        ('persistent_volumes', 'delete'): True,
        ('predefined_apps', 'get'): True,
        ('yaml_pods', 'create'): True,
        ('system_settings', 'read'): True,
        ('images', 'get'): True,
        ('images', 'isalive'): True,
        ('pricing', 'get_own'): True,  # packages, kube types
        ('timezone', 'get'): True,
        ('domains', 'get'): True,
    }),
}
permissions['LimitedUser'] = dict(permissions['User'], **{
    ('pods', 'create'): False,
    ('persistent_volumes', 'create'): False,
})
permissions['TrialUser'] = dict(permissions['User'], **{
    # ...
})

RESOURCES = resources.keys()
PERMISSIONS = [
    (resource, role, action, allowed)
    for role, perms in permissions.iteritems()
    for (resource, action), allowed in perms.iteritems()
    ]


def add_roles(roles=()):
    for r in roles:
        if not Role.filter(Role.rolename == r[0]).first():
            role = Role.create(rolename=r[0], internal=r[1])
            role.save()


def delete_roles(roles=()):
    """Delete roles with its permissions"""
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
    """Delete resources with its permissions"""
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


def _delete_permissions(permissions=()):
    for res, role, perm, allow in permissions:
        resource = Resource.query.filter_by(name=res).first()
        role = Role.query.filter_by(rolename=role).first()
        if role and resource:
            permission = Permission.filter(Permission.role == role). \
                filter(Permission.resource == resource). \
                filter(Permission.allow == allow). \
                filter(Permission.name == perm).first()
            if permission:
                permission.delete()


def add_permissions(roles=None, resources=None, permissions=None):
    if roles:
        add_roles(roles)
    if resources:
        add_resources(resources)
    if permissions:
        _add_permissions(permissions)


def change_permissions(new_permissions):
    """Changes existing permissions.

    Updates all or nothing. If some permission is not found, KeyError raised.

    :raises: KeyError
    """
    for res, role, perm, allow in new_permissions:
        res = Permission.query.join(Role).join(Resource) \
            .filter(Permission.name == perm, Role.rolename == role,
                    Resource.id == Permission.resource_id,
                    Role.id == Permission.role_id,
                    Resource.name == res)\
            .update({'allow': allow}, synchronize_session=False)
        if res == 0:  # there is no updated rows
            db.session.rollback()
            raise KeyError('Permission not found: %s'
                           % [res, role, perm, allow])

    db.session.commit()


def add_all_permissions():
    return add_permissions(ROLES, RESOURCES, PERMISSIONS)


if __name__ == '__main__':
    add_permissions()
