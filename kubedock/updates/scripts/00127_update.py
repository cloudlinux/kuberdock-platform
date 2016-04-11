from kubedock.static_pages.fixtures import (MenuItemRole, MenuItem, Menu,
                                            generate_menu)


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading menu...')
    MenuItemRole.query.delete()
    MenuItem.query.delete()
    Menu.query.delete()
    generate_menu()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrade is not required...')
