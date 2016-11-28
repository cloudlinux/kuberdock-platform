from .. import kdclick
from ..kdclick.access import USER, ADMIN
from ..utils import SimpleCommand


@kdclick.group('stats', available_for=(ADMIN, USER))
@kdclick.pass_obj
def stat(obj):
    """Commands for statistic management"""
    obj.executor = obj.kdctl.stats


@stat.command(available_for=USER)
@kdclick.argument('pod_id', type=str)
@kdclick.pass_obj
class Pod(SimpleCommand):
    """Get statistics of the pod"""
    pass


@stat.command(available_for=(ADMIN, USER))
@kdclick.argument('node_id', type=str)
@kdclick.pass_obj
class Node(SimpleCommand):
    """Get statistics of the container"""
    pass


@stat.command(available_for=USER)
@kdclick.argument('pod_id', type=str)
@kdclick.argument('container_id', type=str)
@kdclick.pass_obj
class Container(SimpleCommand):
    """Get statistics of the node"""
    pass
