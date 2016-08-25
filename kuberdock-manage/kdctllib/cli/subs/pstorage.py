from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN, USER
from ..utils import (SimpleCommand, SimpleCommandWithIdNameArgs,
                     SimpleCommandWithIdNameOwnerArgs)


@kdclick.group(help='Commands for persistent volumes management.',
               available_for=(ADMIN, USER))
@kdclick.pass_context
def pstorage(ctx):
    ctx.obj = ctx.obj.kdctl.pstorage


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required persistent volume')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


###############################################################################
# ADMIN
###############################################################################
@pstorage.command(available_for=ADMIN)
@kdclick.option('--owner')
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@pstorage.command(available_for=ADMIN)
@id_decorator
@kdclick.option('--owner')
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameOwnerArgs):
    pass


@pstorage.command(available_for=ADMIN)
@kdclick.data_argument('device-data')
@kdclick.option('--owner')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@pstorage.command(available_for=ADMIN)
@id_decorator
@kdclick.option('--owner')
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameOwnerArgs):
    pass


###############################################################################
# USER
###############################################################################
@pstorage.command(available_for=USER)
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@pstorage.command(available_for=USER)
@id_decorator
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    pass


@pstorage.command(available_for=USER)
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@pstorage.command(available_for=USER)
@id_decorator
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameArgs):
    pass
