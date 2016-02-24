from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Attempting to add "billing_id" column...')
    helpers.upgrade_db(revision='27c8f4c5f242')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Attempting to delete "billing_id" column...')
    helpers.downgrade_db(revision='4ded025d2f29')