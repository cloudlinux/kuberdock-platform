from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN, USER
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group('system-settings', available_for=(ADMIN, USER))
@kdclick.pass_obj
def ss(obj):
    """Commands for system settings management"""
    obj.executor = obj.kdctl.system_settings


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required system setting')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@ss.command(available_for=(ADMIN, USER))
@kdclick.pass_obj
class List(SimpleCommand):
    """List existing system settings"""
    pass


@ss.command(available_for=(ADMIN, USER))
@id_decorator
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    """Get existing system setting"""
    pass


@ss.command(available_for=ADMIN)
@id_decorator
@kdclick.argument('value')
@kdclick.pass_obj
class Update(SimpleCommandWithIdNameArgs):
    """Update existing system setting"""
    pass
