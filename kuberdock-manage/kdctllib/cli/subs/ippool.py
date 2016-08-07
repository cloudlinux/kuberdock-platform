from .. import kdclick

from ..kdclick.access import ADMIN


@kdclick.group(help='Commands for IP pool management.', available_for=ADMIN)
def ippool():
    pass


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
def list(obj, **params):
    return obj.kdctl.ippool.list(**params)


@ippool.command()
@kdclick.argument('network')
@kdclick.option('--page', type=int, callback=_verify_page)
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.ippool.get(**params)


@ippool.command()
@kdclick.data_argument('ippool-data')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.ippool.create(**params)


@ippool.command()
@kdclick.argument('network')
@kdclick.data_argument('ippool-data')
@kdclick.pass_obj
def update(obj, **params):
    return obj.kdctl.ippool.update(**params)


@ippool.command()
@kdclick.argument('network')
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.ippool.delete(**params)
