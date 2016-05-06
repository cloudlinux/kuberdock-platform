from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Changing session_data schema...')
    helpers.upgrade_db(revision='220dacf65cba')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Restoring session_data schema...')
    helpers.downgrade_db(revision='45e4b1e232ad')