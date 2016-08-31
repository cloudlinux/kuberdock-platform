from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group(help='Commands for users management.', available_for=ADMIN)
@kdclick.pass_obj
def users(obj):
    obj.executor = obj.kdctl.users


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required user')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


class _UsersCommandWithIdNameArgs(SimpleCommandWithIdNameArgs):
    name_field = 'username'


@users.command()
@kdclick.option('--short', is_flag=True)
@kdclick.option('--with-deleted', is_flag=True)
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@users.command()
@id_decorator
@kdclick.option('--short', is_flag=True)
@kdclick.option('--with-deleted', is_flag=True)
@kdclick.pass_obj
class Get(_UsersCommandWithIdNameArgs):
    pass


@users.command()
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@users.command()
@id_decorator
@kdclick.data_argument('data')
@kdclick.pass_obj
class Update(_UsersCommandWithIdNameArgs):
    pass


@users.command()
@id_decorator
@kdclick.option('--force', is_flag=True)
@kdclick.pass_obj
class Delete(_UsersCommandWithIdNameArgs):
    pass
