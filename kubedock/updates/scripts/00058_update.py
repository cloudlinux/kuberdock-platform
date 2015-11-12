from kubedock.updates import helpers
from kubedock.rbac.models import Role


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='3d2db4a87f86')
    upd.print_log('Make HostingPanel role internal...')
    role = Role.filter(Role.rolename == 'HostingPanel').one()
    role.internal = True
    role.save()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='5049471549ba')
