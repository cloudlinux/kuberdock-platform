from kubedock.rbac import fixtures as rbac_fixtures
from kubedock.updates import helpers

revision = '370f6c5fafff'
down_revision = '18b7f1e1988'

new_permissions = [
    ('predefined_apps', 'LimitedUser', 'get', True),
    ('predefined_apps', 'TrialUser', 'get', True),
    ('predefined_apps', 'User', 'get', True),
]

old_permissions = [
    ('predefined_apps', 'LimitedUser', 'get', False),
    ('predefined_apps', 'TrialUser', 'get', False),
    ('predefined_apps', 'User', 'get', False),
]


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading schema...')
    helpers.upgrade_db(revision=revision)
    rbac_fixtures.change_permissions(new_permissions)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading schema...')
    helpers.downgrade_db(revision=down_revision)
    rbac_fixtures.change_permissions(old_permissions)
