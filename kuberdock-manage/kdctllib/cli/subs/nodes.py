from .. import kdclick

from ..kdclick.access import ADMIN


@kdclick.group(help='Commands for nodes management.', available_for=ADMIN)
def nodes():
    pass


@nodes.command()
@kdclick.pass_obj
def list(obj, **params):
    return obj.kdctl.nodes.list(**params)


@nodes.command()
@kdclick.argument('node-id')
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.nodes.get(**params)


@nodes.command()
@kdclick.data_argument('node-data')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.nodes.create(**params)


@nodes.command()
@kdclick.argument('node-id')
@kdclick.data_argument('node-data')
@kdclick.pass_obj
def update(obj, **params):
    return obj.kdctl.nodes.update(**params)


@nodes.command()
@kdclick.argument('node-id')
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.nodes.delete(**params)


@nodes.command('check-host')
@kdclick.argument('hostname')
@kdclick.pass_obj
def check_host(obj, **params):
    return obj.kdctl.nodes.check_host(**params)
