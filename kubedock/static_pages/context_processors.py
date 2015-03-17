from ..static_pages.models import Menu


def pages_helpers():
    context = dict(
        MENU=Menu.get_active(),
    )
    return context
