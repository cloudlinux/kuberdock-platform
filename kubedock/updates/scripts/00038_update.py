from kubedock.core import db
from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='1139a080f512')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='312700b6c892')
