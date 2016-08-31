from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN, USER
from ..utils import (SimpleCommand, SimpleCommandWithIdNameArgs,
                     SimpleCommandWithIdNameOwnerArgs)


@kdclick.group(help='Commands for pods management.',
               available_for=(ADMIN, USER))
@kdclick.pass_obj
def pods(obj):
    obj.executor = obj.kdctl.pods


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required pod')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


###############################################################################
# ADMIN
###############################################################################
@pods.command(available_for=ADMIN)
@kdclick.option('--owner')
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@pods.command(available_for=ADMIN)
@id_decorator
@kdclick.option('--owner')
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameOwnerArgs):
    pass


@pods.command(available_for=ADMIN)
@kdclick.data_argument('data')
@kdclick.option('--owner')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@pods.command(available_for=ADMIN)
@id_decorator
@kdclick.data_argument('data')
# todo: uncomment in api/v2
# @kdclick.option('--owner')  # should be added in api/v2
@kdclick.pass_obj
class Update(SimpleCommandWithIdNameArgs):
    pass


@pods.command(available_for=ADMIN)
@id_decorator
@kdclick.option('--owner')
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameOwnerArgs):
    pass


###############################################################################
# USER
###############################################################################
@pods.command(available_for=USER)
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@pods.command(available_for=USER)
@id_decorator
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    pass


@pods.command(available_for=USER)
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@pods.command(available_for=USER)
@id_decorator
@kdclick.data_argument('data')
# todo: uncomment in api/v2
# @kdclick.option('--owner')  # should be added in api/v2
@kdclick.pass_obj
class Update(SimpleCommandWithIdNameArgs):
    pass


@pods.command(available_for=USER)
@id_decorator
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameArgs):
    pass
