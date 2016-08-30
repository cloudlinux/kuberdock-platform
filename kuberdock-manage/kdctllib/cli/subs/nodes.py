from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group(help='Commands for nodes management.', available_for=ADMIN)
@kdclick.pass_context
def nodes(ctx):
    ctx.obj = ctx.obj.kdctl.nodes


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required node')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@nodes.command()
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@nodes.command()
@id_decorator
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    pass


@nodes.command()
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@nodes.command()
@id_decorator
@kdclick.data_argument('data')
@kdclick.pass_obj
class Update(SimpleCommandWithIdNameArgs):
    pass


@nodes.command()
@id_decorator
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameArgs):
    pass


@nodes.command('check-host')
@kdclick.argument('hostname')
@kdclick.pass_obj
class CheckHost(SimpleCommand):
    corresponding_method = 'check_host'
