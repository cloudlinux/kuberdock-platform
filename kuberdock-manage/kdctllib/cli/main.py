import context
import kdclick
from io import IO
from kdclick.access import ALL
from kdctl import KDCtl
from subs import (images, ippool, nodes, pods, predefined_apps, pricing,
                  pstorage, restore, system_settings, users)
from ..api_client import APIError, UnknownAnswer

settings = context.settings


class ContextObj(object):
    def __init__(self, kdctl=None, io=None):
        """
        :type kdctl: KDCtl
        :type io: IO
        """
        self.kdctl = kdctl
        self.io = io


class Group(kdclick.Group):
    def invoke(self, ctx):
        try:
            return super(Group, self).invoke(ctx)
        except APIError as e:
            ctx.obj.io.out_json(e.json, err=True)
            raise SystemExit(1)
        except UnknownAnswer as e:
            ctx.obj.io.out_json(e.as_dict(), err=True)
            raise SystemExit(1)
        except kdclick.ClickException:
            # caught in super().main()
            raise
        except Exception as e:
            raise SystemExit('Error: %s' % e.message)


@kdclick.group(help=settings.app_description, cls=Group,
               context_settings={
                   'help_option_names': ['-h', '--help']
               })
@kdclick.option('-c', '--config-dir',
                type=kdclick.Path(dir_okay=True, writable=True,
                                  resolve_path=True, allow_dash=True),
                help='Config directory. Default is %s'
                     % settings.working_directory)
@kdclick.option('-d', '--debug', is_flag=True, help='Turn on curl logging.')
@kdclick.option('-j', '--json-only', is_flag=True,
                help='Display json data only, no any additional prompts')
@kdclick.pass_context
def main(ctx, config_dir, debug, json_only):
    if config_dir is None:
        config_dir = settings.working_directory
    kdctl = KDCtl.create(config_dir, debug)
    kdctl.update_config()
    io = IO(json_only)
    ctx.obj = ContextObj(kdctl, io)


@main.resultcallback()
@kdclick.pass_obj
def print_result(obj, result, **params):
    if result is None:
        pass
    else:
        obj.io.out_json(result)


@main.command(help='Login to remote server.', available_for=ALL)
@kdclick.option('-u', '--username', prompt=True)
@kdclick.option('-p', '--password', prompt=True, hide_input=True)
@kdclick.pass_obj
def login(obj, username, password):
    obj.kdctl.login(username, password)


@main.group(help='Commands for config management.', available_for=ALL)
def config():
    pass


@config.command(help='Show current config.', available_for=ALL)
@kdclick.pass_obj
def show(obj):
    return obj.kdctl.config


@config.command(help='Set config key.', available_for=ALL)
@kdclick.argument('key')
@kdclick.argument('value')
@kdclick.pass_obj
def set(obj, key, value):
    obj.kdctl.update_config(**{key: value})
    return obj.kdctl.config


main.add_command(images.images)
main.add_command(ippool.ippool)
main.add_command(nodes.nodes)
main.add_command(pods.pods)
main.add_command(predefined_apps.pa)
main.add_command(pricing.pricing)
main.add_command(pstorage.pstorage)
main.add_command(restore.restore)
main.add_command(system_settings.ss)
main.add_command(users.users)
