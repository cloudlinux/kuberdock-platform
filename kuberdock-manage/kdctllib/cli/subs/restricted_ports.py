from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand


@kdclick.group('restricted-ports', available_for=ADMIN)
@kdclick.pass_obj
def rp(obj):
    """Commands for restricted ports management"""
    obj.executor = obj.kdctl.restricted_ports


@rp.command()
@kdclick.pass_obj
class List(SimpleCommand):
    """Get list of closed ports"""
    pass


@rp.command()
@kdclick.argument('port', type=int)
@kdclick.argument('protocol', default='tcp')
@kdclick.pass_obj
class Close(SimpleCommand):
    """Close port"""
    pass


@rp.command()
@kdclick.argument('port', type=int)
@kdclick.argument('protocol', default='tcp')
@kdclick.pass_obj
class Open(SimpleCommand):
    """Open port"""
    pass
