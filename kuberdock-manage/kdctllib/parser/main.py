import click

from utils import formatted
from . import KDCtl


@click.group(help='Kuberdock admin utilities.', context_settings={
    'allow_interspersed_args': True,
    'allow_extra_args': True,
    'ignore_unknown_options': True,
})
@click.option(
    '-c', '--config-dir',
    type=click.Path(
        exists=True, dir_okay=True, writable=True,
        resolve_path=True, allow_dash=True),
    help='Config directory.')
@click.option('-d', '--debug', is_flag=True, help='Turn on curl logging.')
@click.pass_context
def main(ctx, config_dir, debug):
    if debug:
        import logging
        logging.getLogger('requests_logger').setLevel(logging.DEBUG)
    ctx.obj = KDCtl(config_dir)
    ctx.obj.update_config()


@main.resultcallback()
def print_result(result, **params):
    s = formatted(result)
    if s is not None:
        click.echo(s)


@main.command(help='Login.')
@click.option('-u', '--username')
@click.option('-p', '--password')
@click.pass_obj
def login(obj, username, password):
    obj.login(username, password)


@main.group(help='Commands for config management.')
def config():
    pass


@config.command(help='Show current config.')
@click.pass_obj
def show(obj):
    return obj.config


@config.command(help='Set config key.')
@click.argument('key')
@click.argument('value')
@click.pass_obj
def set(obj, key, value):
    obj.update_config(**{key: value})
    return obj.config
