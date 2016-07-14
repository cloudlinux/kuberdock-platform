import click

from main import main


@main.group('system-settings', help='Commands for system settings management.')
def ss():
    pass


@ss.command()
@click.pass_obj
def list(obj):
    return obj.kdctl.system_settings.list()


@ss.command()
@click.argument('sid')
@click.pass_obj
def get(obj, **params):
    return obj.kdctl.system_settings.get(**params)


@ss.command()
@click.argument('sid')
@click.argument('value')
@click.pass_obj
def update(obj, **params):
    return obj.kdctl.system_settings.update(**params)
