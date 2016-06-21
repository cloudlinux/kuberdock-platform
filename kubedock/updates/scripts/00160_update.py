from kubedock.core import db
from kubedock.rbac.fixtures import add_permissions


def upgrade(upd, with_testing):
    upd.print_log('Update permissions')
    add_permissions()
    db.session.commit()


def downgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Downgrade permissions')
    add_permissions()
    db.session.commit()
