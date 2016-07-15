import click

from main import main


@main.group(help='Commands for pricing management.')
def pricing():
    pass


@pricing.group(help='Commands for license management.')
def license():
    pass


@license.command()
@click.pass_obj
def show(obj):
    return obj.kdctl.pricing.license.show()


@license.command()
@click.argument('installation-id')
@click.pass_obj
def set(obj, **params):
    return obj.kdctl.pricing.license.set(**params)
