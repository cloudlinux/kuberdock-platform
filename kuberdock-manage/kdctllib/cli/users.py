import click

from main import main
from utils import data_argument


@main.group(help='Commands for users management.')
def users():
    pass


@users.command()
@click.option('--short', is_flag=True)
@click.option('--with-deleted', is_flag=True)
@click.pass_obj
def list(obj, **params):
    return obj.kdctl.users.list(**params)


@users.command()
@click.argument('uid')
@click.option('--short', is_flag=True)
@click.option('--with-deleted', is_flag=True)
@click.pass_obj
def get(obj, **params):
    return obj.kdctl.users.get(**params)


@users.command()
@data_argument('user-data')
@click.pass_obj
def create(obj, **params):
    return obj.kdctl.users.create(**params)


@users.command()
@click.argument('uid')
@data_argument('user-data')
@click.pass_obj
def update(obj, **params):
    return obj.kdctl.users.update(**params)


@users.command()
@click.argument('uid')
@click.option('--force', is_flag=True)
@click.pass_obj
def delete(obj, **params):
    return obj.kdctl.users.delete(**params)
