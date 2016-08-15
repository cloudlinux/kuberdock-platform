from kubedock.static_pages.fixtures import Menu, MenuItem, MenuItemRole, Role
from kubedock.static_pages.models import db
from kubedock.settings import AWS


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Adding "Domains" to menus...')

    nav = Menu.query.filter_by(name='Navbar menu').one()
    role = Role.query.filter_by(rolename='Admin').one()
    adm = MenuItem.query.filter_by(name='Administration').one()
    item = MenuItem(name="Domains control", path="#domains", ordering=2)
    item.menu = nav
    item.parent = adm
    item.save()
    item_roles = MenuItemRole(role=role, menuitem=item)
    item_roles.save()

    if AWS:
        ippool = MenuItem.query.filter_by(name='IP pool').first()
        if ippool is not None:
            ippool.name = 'DNS names'
            ippool.save()
        public_ips = MenuItem.query.filter_by(name='Public IPs').first()
        if public_ips is not None:
            public_ips.name = 'Public DNS names'
            public_ips.save()

    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Deleting "Domains" from menus...')

    item = MenuItem.query.filter_by(name='Domains control').first()
    if item is not None:
        item_role = MenuItemRole.query.filter_by(menuitem=item).one()
        item_role.delete()
        item.delete()
        db.session.commit()
