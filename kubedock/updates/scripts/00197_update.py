from kubedock.allowed_ports.models import AllowedPort
from kubedock.core import db
from kubedock.rbac import fixtures


new_resources = [
    'allowed-ports',
]

new_permissions = [
    ('allowed-ports', 'Admin', 'get', True),
    ('allowed-ports', 'Admin', 'create', True),
    ('allowed-ports', 'Admin', 'delete', True),
]


def upgrade(upd, *args, **kwargs):
    upd.print_log('Create table for AllowedPort model if not exists')
    AllowedPort.__table__.create(bind=db.engine, checkfirst=True)
    upd.print_log('Upgrade permissions')
    fixtures.add_permissions(resources=new_resources,
                             permissions=new_permissions)


def downgrade(upd, *args, **kwargs):
    pass
