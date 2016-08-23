from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading schema...')
    helpers.upgrade_db(revision='8d3aed3e74c')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading schema...')
    helpers.downgrade_db(revision='370f6c5fafff')
