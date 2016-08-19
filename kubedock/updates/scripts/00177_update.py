from kubedock.updates import helpers

revision = '370f6c5fafff'
down_revision = '18b7f1e1988'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading schema...')
    helpers.upgrade_db(revision=revision)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading schema...')
    helpers.downgrade_db(revision=down_revision)
