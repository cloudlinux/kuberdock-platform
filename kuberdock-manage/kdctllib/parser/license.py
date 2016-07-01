import click

from main import main
# from utils import data_argument


@main.group(help='Commands for license management.')
def license():
    pass


@license.command()
@click.pass_obj
def show(obj):
    return obj.client.license.show()


@license.command()
@click.option('-l', '--license')
@click.pass_obj
def set(obj, license):
    return obj.client.license.set(license)
