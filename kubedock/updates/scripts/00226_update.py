from kubedock.updates import helpers


def upgrade(upd, *args, **kwargs):
    upd.print_log('Upgrading nodes table...')
    helpers.upgrade_db(revision='570768aed03e')


def downgrade(upd, *args, **kwargs):
    upd.print_log('Downgrading nodes table...')
    helpers.downgrade_db(revision='1f26cf5abc0f')
