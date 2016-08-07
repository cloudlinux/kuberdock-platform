from .. import kdclick

from ..kdclick.access import ADMIN


@kdclick.group(help='Commands for users management.', available_for=ADMIN)
def users():
    pass


@users.command()
@kdclick.option('--short', is_flag=True)
@kdclick.option('--with-deleted', is_flag=True)
@kdclick.pass_obj
def list(obj, **params):
    return obj.kdctl.users.list(**params)


@users.command()
@kdclick.argument('uid')
@kdclick.option('--short', is_flag=True)
@kdclick.option('--with-deleted', is_flag=True)
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.users.get(**params)


@users.command()
@kdclick.data_argument('user-data')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.users.create(**params)


@users.command()
@kdclick.argument('uid')
@kdclick.data_argument('user-data')
@kdclick.pass_obj
def update(obj, **params):
    return obj.kdctl.users.update(**params)


@users.command()
@kdclick.argument('uid')
@kdclick.option('--force', is_flag=True)
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.users.delete(**params)
