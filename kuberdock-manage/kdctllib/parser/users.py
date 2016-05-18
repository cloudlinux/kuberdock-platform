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
def list(obj, short, with_deleted):
    return obj.client.users.list(short, with_deleted)


@users.command()
@click.argument('uid')
@click.option('--short', is_flag=True)
@click.option('--with-deleted', is_flag=True)
@click.pass_obj
def get(obj, uid, short, with_deleted):
    return obj.client.users.get(uid, short, with_deleted)


@users.command()
@data_argument('user-data')
@click.pass_obj
def create(obj, user_data):
    return obj.client.users.create(user_data)


@users.command()
@click.argument('uid')
@data_argument('user-data')
@click.pass_obj
def update(obj, uid, user_data):
    return obj.client.users.update(uid, user_data)


@users.command()
@click.argument('uid')
@click.option('--force', is_flag=True)
@click.pass_obj
def delete(obj, uid, force):
    return obj.client.users.delete(uid, force)
