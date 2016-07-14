import click

from main import main
from utils import data_argument


@main.group('predefined-apps',
            help='Commands for predefined applications management.')
def pa():
    pass


@pa.command()
@click.option('--file-only', is_flag=True)
@click.pass_obj
def list(obj, **params):
    return obj.kdctl.predefined_apps.list(**params)


@pa.command()
@click.argument('app-id')
@click.option('--file-only', is_flag=True)
@click.pass_obj
def get(obj, **params):
    return obj.kdctl.predefined_apps.get(**params)


@pa.command()
@data_argument('app-data')
@click.pass_obj
def create(obj, **params):
    return obj.kdctl.predefined_apps.create(**params)


@pa.command()
@click.argument('app-id')
@data_argument('app-data')
@click.pass_obj
def update(obj, **params):
    return obj.kdctl.predefined_apps.update(**params)


@pa.command()
@click.argument('app-id')
@click.pass_obj
def delete(obj, **params):
    return obj.kdctl.predefined_apps.delete(**params)


@pa.command('validate-template')
@data_argument('template')
@click.pass_obj
def validate_template(obj, **params):
    return obj.kdctl.predefined_apps.validate_template(**params)
