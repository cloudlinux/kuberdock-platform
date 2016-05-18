import click

from main import main
from utils import data_argument


@main.group(
    'predefined-apps',
    help='Commands for predefined applications management.')
def pa():
    pass


@pa.command()
@click.option('--file-only', is_flag=True)
@click.pass_obj
def list(obj, file_only):
    return obj.client.predefined_apps.list(file_only)


@pa.command()
@click.argument('app-id')
@click.option('--file-only', is_flag=True)
@click.pass_obj
def get(obj, app_id, file_only):
    return obj.client.predefined_apps.get(app_id, file_only)


@pa.command()
@data_argument('app-data')
@click.pass_obj
def create(obj, app_data):
    return obj.client.predefined_apps.create(app_data)


@pa.command()
@click.argument('app-id')
@data_argument('app-data')
@click.pass_obj
def update(obj, app_id, app_data):
    return obj.client.predefined_apps.update(app_id, app_data)


@pa.command()
@click.argument('app-id')
@click.pass_obj
def delete(obj, app_id):
    return obj.client.predefined_apps.delete(app_id)


@pa.command('validate-template')
@data_argument('template')
@click.pass_obj
def validate_template(obj, template):
    return obj.client.predefined_apps.validate_template(template)
