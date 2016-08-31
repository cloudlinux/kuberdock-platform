from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand


@kdclick.group(help='Commands for IP pool management.', available_for=ADMIN)
@kdclick.pass_obj
def ippool(obj):
    obj.executor = obj.kdctl.ippool


def _verify_page(ctx, param, value):
    conditions = [
        value is None or value > 0
    ]
    if not all(conditions):
        raise kdclick.BadParameter('Page must be greater than 0.')
    return value


@ippool.command()
@kdclick.option('--page', type=int, callback=_verify_page)
@kdclick.option('--free-only', is_flag=True)
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@ippool.command()
@kdclick.argument('network')
@kdclick.option('--page', type=int, callback=_verify_page)
@kdclick.pass_obj
class Get(SimpleCommand):
    pass


@ippool.command()
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@ippool.command()
@kdclick.argument('network')
@kdclick.data_argument('data')
@kdclick.pass_obj
class Update(SimpleCommand):
    pass


@ippool.command()
@kdclick.argument('network')
@kdclick.pass_obj
class Delete(SimpleCommand):
    pass
