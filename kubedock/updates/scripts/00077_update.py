from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Clear cache...')
    from kubedock.core import ConnectionPool
    redis = ConnectionPool.get_connection()
    redis.delete('KDCOLLECTION')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('No downgrade needed')
