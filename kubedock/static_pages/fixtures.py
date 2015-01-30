from .models import Menu, MenuItem, Page

MENUS = [
    dict(
        region=Menu.REGION_NAVBAR,
        name='Navbar menu',
        items=[
            dict(
                name='Administrative',
                children=[
                    dict(
                        path='/users/',
                        name='User list',
                    ),
                    dict(
                        path='/users/online',
                        name='Online user list',
                    ),
                    dict(
                        name='Static pages and menus',
                        children=[
                            dict(
                                path='/admin/static_pages/menus/',
                                name='Menus'
                            ),
                            dict(
                                path='/admin/static_pages/menus/pages/',
                                name='Pages'
                            ),
                        ]
                    ),
                    dict(
                        path='/admin/static_pages/menus/pages/TestStaticPage',
                        name='Test static page',
                        page=dict(
                            title='Test static page',
                            slug='TestStaticPage',
                            content="<h1>Test static page</h1>"
                        )
                    ),
                    dict(
                        path='/admin/static_pages/menus/pages/FAQ',
                        name='FAQ',
                        page=dict(
                            title='FAQ',
                            slug='FAQ',
                            content="<h1>FAQ</h1>"
                        )
                    )
                ]
            )
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

    for menu in MENUS:
        items = menu.pop('items')
        menu = Menu.create(**menu)
        menu.save()
        for item in items:
            children = item.pop('children')
            menu_item = MenuItem(**item)
            menu_item.menu = menu
            menu_item.save()
            create_children(children, menu_item, menu)


if __name__ == '__main__':
    # Generate menus, menu items and test pages
    generate_menu()