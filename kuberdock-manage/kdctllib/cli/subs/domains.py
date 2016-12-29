from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN, USER
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group(available_for=(ADMIN, USER))
@kdclick.pass_obj
def domains(obj):
    """Commands for domains management"""
    obj.executor = obj.kdctl.domains


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required domain')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@domains.command(available_for=(ADMIN, USER))
@kdclick.pass_obj
class List(SimpleCommand):
    """List all existing domains"""
    pass


@domains.command(available_for=(ADMIN, USER))
@id_decorator
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    """Get existing domain"""
    pass


@domains.command(available_for=(ADMIN,))
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    """Create new domain"""
    pass


@domains.command(available_for=(ADMIN,))
@id_decorator
@kdclick.data_argument('data')
@kdclick.pass_obj
class Update(SimpleCommandWithIdNameArgs):
    """Update existing domain"""
    pass


@domains.command(available_for=(ADMIN,))
@id_decorator
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameArgs):
    """Delete existing domain"""
    pass
