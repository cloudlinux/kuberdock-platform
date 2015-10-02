from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Reloading nginx...')
    helpers.local('nginx -s reload')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Reloading nginx...')
    helpers.local('nginx -s reload')
