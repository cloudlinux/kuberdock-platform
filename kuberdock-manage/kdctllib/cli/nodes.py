import click

from main import main
from utils import data_argument


@main.group(help='Nodes management.')
def nodes():
    pass


@nodes.command()
@click.pass_obj
def list(obj, **params):
    return obj.kdctl.nodes.list(**params)


@nodes.command()
@click.argument('node-id')
@click.pass_obj
def get(obj, **params):
    return obj.kdctl.nodes.get(**params)


@nodes.command()
@data_argument('node-data')
@click.pass_obj
def create(obj, **params):
    return obj.kdctl.nodes.create(**params)


@nodes.command()
@click.argument('node-id')
@data_argument('node-data')
@click.pass_obj
def update(obj, **params):
    return obj.kdctl.nodes.update(**params)


@nodes.command()
@click.argument('node-id')
@click.pass_obj
def delete(obj, **params):
    return obj.kdctl.nodes.delete(**params)


@nodes.command('check-host')
@click.argument('hostname')
@click.pass_obj
def check_host(obj, **params):
    return obj.kdctl.nodes.check_host(**params)
