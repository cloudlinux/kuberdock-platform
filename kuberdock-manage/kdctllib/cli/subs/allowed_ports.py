from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand


@kdclick.group('allowed-ports', available_for=ADMIN)
@kdclick.pass_obj
def ap(obj):
    """Commands for allowed ports management"""
    obj.executor = obj.kdctl.allowed_ports


@ap.command()
@kdclick.pass_obj
class List(SimpleCommand):
    """Get list of opened ports"""
    pass


@ap.command()
@kdclick.argument('port', type=int)
@kdclick.argument('protocol', default='tcp')
@kdclick.pass_obj
class Open(SimpleCommand):
    """Open port"""
    pass


@ap.command()
@kdclick.argument('port', type=int)
@kdclick.argument('protocol', default='tcp')
@kdclick.pass_obj
class Close(SimpleCommand):
    """Close port"""
    pass
