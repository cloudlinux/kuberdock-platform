from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils.misc import SimpleCommand


@kdclick.group(available_for=ADMIN)
def pricing():
    """Commands for pricing management"""
    pass


@pricing.group()
@kdclick.pass_obj
def license(obj):
    """Commands for license management"""
    obj.executor = obj.kdctl.pricing.license


@license.command()
@kdclick.pass_obj
class Show(SimpleCommand):
    """Show existing license"""
    pass


@license.command()
@kdclick.argument('installation-id')
@kdclick.pass_obj
class Set(SimpleCommand):
    """Set new installation id"""
    pass
