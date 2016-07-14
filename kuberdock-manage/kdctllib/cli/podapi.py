import click

from main import main
from utils import data_argument


@main.group(help='Commands for pods management.')
def pods():
    pass


@pods.command()
@click.option('--owner')
@click.pass_obj
def list(obj, **params):
    return obj.kdctl.pods.list(**params)


@pods.command()
@click.argument('pod-id')
@click.option('--owner')
@click.pass_obj
def get(obj, **params):
    return obj.kdctl.pods.get(**params)


@pods.command()
@data_argument('pod-data')
@click.option('--owner')
@click.pass_obj
def create(obj, **params):
    return obj.kdctl.pods.create(**params)


@pods.command()
@click.argument('pod-id')
@data_argument('pod-data')
# todo: uncomment in api/v2
# @click.option('--owner')  # should be added in api/v2
@click.pass_obj
def update(obj, **params):
    return obj.kdctl.pods.update(**params)


@pods.command()
@click.argument('pod-id')
@click.option('--owner')
@click.pass_obj
def delete(obj, **params):
    return obj.kdctl.pods.delete(**params)
