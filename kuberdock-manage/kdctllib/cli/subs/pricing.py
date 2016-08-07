from .. import kdclick
from ..kdclick.access import ADMIN


@kdclick.group(help='Commands for pricing management.', available_for=ADMIN)
def pricing():
    pass


@pricing.group(help='Commands for license management.')
def license():
    pass


@license.command()
@kdclick.pass_obj
def show(obj):
    return obj.kdctl.pricing.license.show()


@license.command()
@kdclick.argument('installation-id')
@kdclick.pass_obj
def set(obj, **params):
    return obj.kdctl.pricing.license.set(**params)
