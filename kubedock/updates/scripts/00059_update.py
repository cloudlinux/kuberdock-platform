from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='2e00e70316c0')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='3d2db4a87f86')
