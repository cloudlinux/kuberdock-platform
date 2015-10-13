from kubedock.updates import helpers
from kubedock.core import db
from kubedock.rbac.models import Permission, Role, Resource


ACTIONS = ('read', 'write', 'delete')

def add_permissions():
    admin_role = db.session.query(Role.id).filter(
        Role.rolename == 'Admin'
    ).first()
    resource = db.session.query(Resource).filter(
        Resource.name == 'system_settings'
    ).first()
    if not resource:
        resource = Resource(name='system_settings')
        db.session.add(resource)
        db.session.flush()
    db.session.add_all([
        Permission(resource_id=resource.id, role_id=admin_role.id,
                   name=name, allow=True)
        for name in ACTIONS
    ])
    db.session.commit()

def drop_permissions():
    admin_role = db.session.query(Role.id).filter(
        Role.rolename == 'Admin'
    ).first()
    resource = db.session.query(Resource).filter(
        Resource.name == 'system_settings'
    ).first()
    if not resource:
        return
    db.session.query(Permission).filter(
        Permission.resource_id == resource.id,
        Permission.role_id == admin_role.id,
        Permission.name.in_(ACTIONS)
    ).delete()
    db.session.commit()


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add permissions to system settings ...')
    add_permissions()
    helpers.upgrade_db(revision='589e137e4b7c')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Delete permissions to system settings ...')
    drop_permissions()
    helpers.downgrade_db()
