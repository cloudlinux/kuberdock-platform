from copy import deepcopy
import json
from .models import Menu, MenuItem, Page

MENUS = [
    dict(
        region=Menu.REGION_NAVBAR,
        name='Navbar menu',
        items=[
            dict(name="Pods", path="/", ordering=0, roles=json.dumps(["User", "TrialUser"])),
            dict(name="Public IPs", path="/publicIPs/", ordering=1, roles=json.dumps(["User", "TrialUser"])),
            dict(name="Persistent volumes", path="/persistent-volumes/", ordering=2, roles=json.dumps(["User", "TrialUser"])),
            dict(name="Nodes", path="/nodes/", ordering=1,
                 roles=json.dumps(["Admin"])),
            dict(name="Predefined Applications", path="/predefined-apps/", ordering=2,
                 roles=json.dumps(["Admin"])),
            # dict(name="Users", path="/users/", ordering=2,
            #      roles=json.dumps(["Admin"])),
            # dict(
            #     name="Helpdesk",
            #     children=[
            #         dict(
            #             name="FAQ",
            #             page=dict(
            #                 title="FAQ",
            #                 slug="FAQ",
            #                 content="<h1>Helpdesk</h1>"
            #                         "<p>text here</p>"
            #                         "<i>Static page sample</i>"
            #             ),
            #             ordering=0
            #         )
            #     ],
            #     ordering=3
            # ),
            dict(name="Settings", path="/settings/", ordering=4),
            dict(
                name="Administration",
                ordering=5,
                children=[
                    dict(name="Users", path="/users/", ordering=0),
                    dict(name="IP pool", path="/ippool/", ordering=1),
                    # dict(name="Notifications", path="/notifications/",
                    #      ordering=2),
                    # dict(name="Static pages and menus",
                    #      path='/admin/static_pages/',
                    #      ordering=3)
                ],
                roles=json.dumps(["Admin"])
            ),
        ]
    ),
    dict(
        region=Menu.REGION_FOOTER,
        name='Footer menu',
        items=[
            dict(name='expample page')
        ]
    )
]


def generate_menu():

    def create_children(children, parent, menu):
        for item in children:
            _children = item.pop('children', None)
            p = item.pop('path', None)
            _page = item.pop('page', None)
            menu_item = MenuItem(**item)
            menu_item.menu = menu
            menu_item.path = p
            menu_item.parent = parent
            if _page:
                path = _page.pop('page', None)
                page = Page(**_page)
                page.path = path
                page.save()
                menu_item.page = page
            menu_item.save()
            if _children:
                create_children(_children, menu_item, menu)

    menus = deepcopy(MENUS)
    for menu in menus:
        items = menu.pop('items')
        menu = Menu.create(**menu)
        menu.save()
        for item in items:
            children = item.pop('children', None)
            menu_item = MenuItem(**item)
            menu_item.menu = menu
            menu_item.save()
            if children:
                create_children(children, menu_item, menu)


if __name__ == '__main__':
    # Generate menus, menu items and test pages
    generate_menu()
