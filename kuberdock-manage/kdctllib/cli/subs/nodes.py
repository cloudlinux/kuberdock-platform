from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group(help='Commands for nodes management.', available_for=ADMIN)
@kdclick.pass_obj
def nodes(obj):
    obj.executor = obj.kdctl.nodes


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required node')
    @kdclick.option('--hostname',
                    help='Use it to specify hostname instead of id')
    @kdclick.required_exactly_one_of('id', 'hostname')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


class NodesCommandWithIdNameArgs(SimpleCommandWithIdNameArgs):
    name_field = 'hostname'
    name_kwarg = 'hostname'


@nodes.command()
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@nodes.command()
@id_decorator
@kdclick.pass_obj
class Get(NodesCommandWithIdNameArgs):
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
class Update(NodesCommandWithIdNameArgs):
    pass


@nodes.command()
@id_decorator
@kdclick.pass_obj
class Delete(NodesCommandWithIdNameArgs):
    pass


@nodes.command('check-host')
@kdclick.argument('hostname')
@kdclick.pass_obj
class CheckHost(SimpleCommand):
    corresponding_method = 'check_host'
