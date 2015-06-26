from kubedock.updates.helpers import print_log, upgradedb

# Update scripts must be verbose


def upgrade(upd, with_testing, *args, **kwargs):
    print_log(upd, 'upgrade 1')
    upgradedb()


def downgrade(upd, with_testing, *args, **kwargs):
    print_log(upd, 'downgrade 1')
