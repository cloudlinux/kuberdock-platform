from collections import namedtuple

import click

from . import KDCtl, IO
from ..kdclient.exceptions import APIError, UnknownAnswer

ContextObj = namedtuple('ContextObj', ('kdctl', 'io'))


class MainGroup(click.Group):
    def invoke(self, ctx):
        try:
            return super(MainGroup, self).invoke(ctx)
        except APIError as e:
            ctx.obj.io.out_json(e.json, err=True)
            raise SystemExit(1)
        except UnknownAnswer as e:
            ctx.obj.io.out_json(e.as_dict(), err=True)
            raise SystemExit(1)
        except click.ClickException:
            # caught in super().main()
            raise
        except Exception as e:
            raise SystemExit('Error: ' + repr(e))


@click.group(help='Kuberdock admin utilities.', cls=MainGroup,
             context_settings={
                 'help_option_names': ['-h', '--help']
             })
@click.option(
    '-c', '--config-dir',
    type=click.Path(
        exists=True, dir_okay=True, writable=True,
        resolve_path=True, allow_dash=True),
    help='Config directory.')
@click.option('-d', '--debug', is_flag=True, help='Turn on curl logging.')
@click.option('-j', '--json-only', is_flag=True,
              help='Display json data only, no any additional prompts')
@click.pass_context
def main(ctx, config_dir, debug, json_only):
    kdctl = KDCtl(config_dir, debug)
    kdctl.update_config()
    io = IO(json_only)
    ctx.obj = ContextObj(kdctl, io)


@main.resultcallback()
@click.pass_obj
def print_result(obj, result, **params):
    if result is None:
        pass
    elif isinstance(result, dict):
        obj.io.out_json(result)
    else:
        obj.io.out_text(str(result))


@main.command(help='Login to remote server.')
@click.option('-u', '--username')
@click.option('-p', '--password')
@click.pass_obj
def login(obj, username, password):
    if not username:
        username = obj.io.prompt('Username')
        password = obj.io.prompt('Password', hide_input=True)
    elif not password:
        password = obj.io.prompt('Password', hide_input=True)
    obj.kdctl.login(username, password)


@main.group(help='Commands for config management.')
def config():
    pass


@config.command(help='Show current config.')
@click.pass_obj
def show(obj):
    return obj.kdctl.config


@config.command(help='Set config key.')
@click.argument('key')
@click.argument('value')
@click.pass_obj
def set(obj, key, value):
    obj.kdctl.update_config(**{key: value})
    return obj.kdctl.config
