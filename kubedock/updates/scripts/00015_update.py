from kubedock.core import db
from kubedock.rbac.models import Permission, Role, Resource


def _set_permission(value):
    resources = db.session.query(Resource.id).filter(
        Resource.name == 'ippool').subquery()
    roles = db.session.query(Role.id).filter(
        Role.rolename.in_(('User', 'TrialUser'))).subquery()
    Permission.query.filter(
        Permission.name.in_(('get', 'view')),
        # there are some problems with join in update, use subquery instead
        Permission.resource_id.in_(resources),
        Permission.role_id.in_(roles)
    ).update({Permission.allow: value}, synchronize_session=False)
    db.session.commit()


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Forbid user to see ip pool...')
    _set_permission(False)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Allow user to see ip pool...')
    _set_permission(True)
