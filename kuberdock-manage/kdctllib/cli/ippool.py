import click

from main import main
from utils import data_argument


@main.group(help='IP pool management.')
def ippool():
    pass


def _verify_page(ctx, param, value):
    conditions = [
        value is None or value > 0
    ]
    if not all(conditions):
        raise click.BadParameter('Page must be greater than 0.')
    return value


@ippool.command()
@click.option('--page', type=int, callback=_verify_page)
@click.option('--free-only', is_flag=True)
@click.pass_obj
def list(obj, **params):
    return obj.kdctl.ippool.list(**params)


@ippool.command()
@click.argument('network')
@click.option('--page', type=int, callback=_verify_page)
@click.pass_obj
def get(obj, **params):
    return obj.kdctl.ippool.get(**params)


@ippool.command()
@data_argument('ippool-data')
@click.pass_obj
def create(obj, **params):
    return obj.kdctl.ippool.create(**params)


@ippool.command()
@click.argument('network')
@data_argument('ippool-data')
@click.pass_obj
def update(obj, **params):
    return obj.kdctl.ippool.update(**params)


@ippool.command()
@click.argument('network')
@click.pass_obj
def delete(obj, **params):
    return obj.kdctl.ippool.delete(**params)
