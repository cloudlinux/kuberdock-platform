from kubedock.static_pages.models import MenuItem, db


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Fix urls in main menu...')
    for item in MenuItem.query.all():
        if item.path:
            item.path = item.path.replace('/', '#', 1).rstrip('/')
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Return old urls')
    for item in MenuItem.query.all():
        if item.path:
            item.path = '{0}/'.format(item.path.replace('#', '/', 1))
    db.session.commit()
