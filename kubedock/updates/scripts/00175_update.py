from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading schema...')
    helpers.upgrade_db(revision='18b7f1e1988')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading schema...')
    helpers.downgrade_db(revision='12963e26b673')
