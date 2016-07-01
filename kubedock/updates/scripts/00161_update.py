from kubedock.updates import helpers

def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading DB...')
    helpers.upgrade_db(revision='12963e26b673')

def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrade DB...')
    helpers.downgrade_db(revision='1a24688cc541')
