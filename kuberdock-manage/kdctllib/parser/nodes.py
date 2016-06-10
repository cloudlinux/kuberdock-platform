import click

from main import main
from utils import data_argument


@main.group(help='Nodes management.')
def nodes():
    pass


@nodes.command()
@click.pass_obj
def list(obj):
    return obj.client.nodes.list()


@nodes.command()
@click.argument('node-id')
@click.pass_obj
def get(obj, node_id):
    return obj.client.nodes.get(node_id)


@nodes.command()
@data_argument('node-data')
@click.pass_obj
def create(obj, node_data):
    return obj.client.nodes.create(node_data)


@nodes.command()
@click.argument('node-id')
@data_argument('node-data')
@click.pass_obj
def update(obj, node_id, node_data):
    return obj.client.nodes.update(node_id, node_data)


@nodes.command()
@click.argument('node-id')
@click.pass_obj
def delete(obj, node_id):
    return obj.client.nodes.delete(node_id)


@nodes.command('check-host')
@click.argument('hostname')
@click.pass_obj
def check_host(obj, hostname):
    return obj.client.nodes.check_host(hostname)
