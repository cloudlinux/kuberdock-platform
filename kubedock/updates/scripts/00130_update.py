from kubedock.rbac.fixtures import Permission, Resource, add_permissions
from kubedock.users.models import db


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update permissions...')
    Permission.query.delete()
    Resource.query.delete()
    add_permissions()
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('No downgrade needed...')
