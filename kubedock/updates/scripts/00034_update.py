import json

from kubedock.core import db

from kubedock.static_pages.models import Menu, MenuItem


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add "Predefined Applications" menu item...')
    menu = Menu.query.filter_by(region=Menu.REGION_NAVBAR).first()
    menu_item = MenuItem(name='Predefined Applications', menu=menu, ordering=2,
                         path='/predefined-apps/', roles=json.dumps(['Admin']))
    db.session.add(menu_item)
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Remove "Predefined Applications" menu item...')
    menu_item = MenuItem.query.filter_by(name='Predefined Applications').first()
    db.session.delete(menu_item)
    db.session.commit()
