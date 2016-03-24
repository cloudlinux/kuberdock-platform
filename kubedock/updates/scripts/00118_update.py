from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Changing package count_type column...')
    helpers.upgrade_db(revision='2c64986d76b9')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Reverting package count_type column...')
    helpers.downgrade_db(revision='42b36be03945')