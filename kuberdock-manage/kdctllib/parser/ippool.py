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
def list(obj, page, free_only):
    return obj.client.ippool.list(page=page, free_only=free_only)


@ippool.command()
@click.argument('network')
@click.option('--page', type=int, callback=_verify_page)
@click.pass_obj
def get(obj, network, page):
    return obj.client.ippool.get(network=network, page=page)


@ippool.command()
@data_argument('ippool-data')
@click.pass_obj
def create(obj, ippool_data):
    return obj.client.ippool.create(ippool_data=ippool_data)


@ippool.command()
@click.argument('network')
@data_argument('ippool-data')
@click.pass_obj
def update(obj, network, ippool_data):
    return obj.client.ippool.update(network=network, ippool_data=ippool_data)


@ippool.command()
@click.argument('network')
@click.pass_obj
def delete(obj, network):
    return obj.client.ippool.delete(network=network)
