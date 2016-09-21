from kubedock.rbac.models import Resource, Permission, Role


def upgrade(upd, with_testing, *args, **kwargs):
    resource = Resource.query.filter(
        Resource.name == 'predefined_apps').first()
    roles_ids = [role.id for role in Role.filter(Role.rolename != 'Admin')]
    admin_role = Role.filter_by(rolename='Admin').first()

    Permission(
        resource_id=resource.id,
        name='get_unavailable',
        role_id=admin_role.id,
        allow=True
    ).save()

    for role_id in roles_ids:
        Permission(
            resource_id=resource.id,
            name='get_unavailable',
            role_id=role_id,
            allow=False
        ).save()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    resource = Resource.query.filter(
        Resource.name == 'predefined_apps').first()

    Permission.query.filter_by(name='get_unavailable',
                               resource_id=resource.id)\
        .delete(synchronize_session='fetch')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass