from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Forbid null in User.package_id field...')
    helpers.upgrade_db(revision='45e4b1e232ad')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Allow null in User.package_id field...')
    helpers.downgrade_db(revision='2c64986d76b9')
