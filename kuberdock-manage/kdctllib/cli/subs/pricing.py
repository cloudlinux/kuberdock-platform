from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils.misc import SimpleCommand


@kdclick.group(help='Commands for pricing management.', available_for=ADMIN)
def pricing():
    pass


@pricing.group(help='Commands for license management.')
@kdclick.pass_obj
def license(obj):
    obj.executor = obj.kdctl.pricing.license


@license.command()
@kdclick.pass_obj
class Show(SimpleCommand):
    pass


@license.command()
@kdclick.argument('installation-id')
@kdclick.pass_obj
class Set(SimpleCommand):
    pass
