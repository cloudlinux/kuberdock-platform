from ..static_pages.models import MenuItem


def pages_helpers():
    context = dict(
        MENU=MenuItem.get_menu()
    )
    return context
