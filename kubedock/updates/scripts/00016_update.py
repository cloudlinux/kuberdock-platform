from kubedock.rbac.models import Permission, Resource, Role


def _set_new(val):
    role = Role.filter_by(rolename='Admin').first()
    pod_res = Resource.filter_by(name='pods').first()
    perms = Permission.filter_by(role_id=role.id, resource_id=pod_res.id).all()
    for perm in perms:
        if val:
            perm.set_allow()
        else:
            perm.set_deny()


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log("Disable admin's pods permissions")
    _set_new(False)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log("Reenable admin's pods permissions")
    _set_new(True)
