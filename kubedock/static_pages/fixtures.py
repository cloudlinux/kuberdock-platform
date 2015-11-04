from copy import deepcopy
from .models import Menu, MenuItem, MenuItemRole
from kubedock.rbac.models import Role


MENUS = [
    dict(
        region=Menu.REGION_NAVBAR,
        name='Navbar menu',
        items=[
            dict(name="Pods", path="/", ordering=0,
                 roles=["User", "TrialUser"]),
            dict(name="Public IPs", path="/publicIPs/", ordering=1,
                 roles=["User", "TrialUser"]),
            dict(name="Persistent volumes", path="/persistent-volumes/",
                 ordering=2, roles=["User", "TrialUser"]),
            dict(name="Nodes", path="/nodes/", ordering=1, roles=["Admin"]),
            dict(name="Predefined Applications", path="/predefined-apps/",
                 ordering=2, roles=["Admin"]),
            dict(name="Settings", path="/settings/", ordering=4,
                 roles=["Admin", "User", "TrialUser"]),
            dict(
                name="Administration",
                ordering=5,
                children=[
                    dict(name="Users", path="/users/", ordering=0,
                         roles=["Admin"]),
                    dict(name="IP pool", path="/ippool/", ordering=1,
                         roles=["Admin"]),
                ],
                roles=["Admin"]
            ),
        ]
    ),
]


def generate_menu():

    def add_menu_items(items, menu, parent=None,):
        for item in items:
            roles = item.pop('roles', [])
            children = item.pop('children', None)
            menu_item = MenuItem(**item)
            menu_item.menu = menu
            menu_item.parent = parent
            menu_item.save()
            for rolename in roles:
                role = Role.filter(Role.rolename == rolename).one()
                item_role = MenuItemRole(role=role, menuitem=menu_item)
                item_role.save()
            if children:
                add_menu_items(children, menu, parent=menu_item)

    menus = deepcopy(MENUS)
    for menu in menus:
        items = menu.pop('items')
        menu = Menu.create(**menu)
        menu.save()
        add_menu_items(items, menu)


if __name__ == '__main__':
    # Generate menus, menu items
    generate_menu()
