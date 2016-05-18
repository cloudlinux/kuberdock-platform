import click

from main import main


@main.group('system-settings', help='Commands for system settings management.')
def ss():
    pass


@ss.command()
@click.pass_obj
def list(obj):
    return obj.client.system_settings.list()


@ss.command()
@click.argument('sid')
@click.pass_obj
def get(obj, sid):
    return obj.client.system_settings.get(sid)


@ss.command()
@click.argument('sid')
@click.argument('value')
@click.pass_obj
def update(obj, sid, value):
    return obj.client.system_settings.update(sid, value)
