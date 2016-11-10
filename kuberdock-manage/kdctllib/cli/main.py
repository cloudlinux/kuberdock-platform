import context
import kdclick
from io import IO
from kdclick.access import ALL
from kdctl import KDCtl
from subs import (
    allowed_ports,
    domains,
    images,
    ippool,
    nodes,
    pods,
    predefined_apps,
    pricing,
    pstorage,
    system_settings,
    users,
)
from utils.misc import ContextObj
from ..api_client import APIError, UnknownAnswer

settings = context.settings


def _disable_requests_warnings():
    import requests
    requests.packages.urllib3.disable_warnings()


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
               context_settings={'help_option_names': ['-h', '--help']})
@kdclick.option('-c', '--config-dir',
                type=kdclick.Path(dir_okay=True, writable=True,
                                  resolve_path=True, allow_dash=True),
                help='Config directory. Default is %s'
                     % settings.working_directory)
@kdclick.option('-d', '--debug', is_flag=True,
                help='Log all HTTP requests as cURL')
@kdclick.option('-j', '--json-only', is_flag=True,
                help='Display json data only, no any additional prompts')
@kdclick.option('-k', '--no-http-warnings', is_flag=True,
                help='Disable HTTP warnings')
@kdclick.pass_context
def main(ctx, config_dir, debug, json_only, no_http_warnings):
    if no_http_warnings:
        _disable_requests_warnings()
    if config_dir is None:
        config_dir = settings.working_directory
    kdctl = KDCtl.create(config_dir, debug)
    kdctl.update_config()
    io = IO(json_only)
    ctx_obj = ContextObj()
    ctx_obj.kdctl = kdctl
    ctx_obj.io = io
    ctx.obj = ctx_obj


@main.resultcallback()
@kdclick.pass_obj
def print_result(obj, result, **params):
    if result is None:
        pass
    else:
        obj.io.out_json(result)


@main.command(available_for=ALL)
@kdclick.option('-u', '--username', prompt=True, help='Kuberdock user name')
@kdclick.option('-p', '--password', prompt=True, hide_input=True,
                help='Kuberdock user password')
@kdclick.pass_obj
def login(obj, username, password):
    """Login to remote server"""
    obj.kdctl.login(username, password)


@main.group(available_for=ALL)
def config():
    """Commands for config management"""
    pass


@config.command(available_for=ALL)
@kdclick.pass_obj
def show(obj):
    """Show current config"""
    return obj.kdctl.config


@config.command(available_for=ALL)
@kdclick.argument('key')
@kdclick.argument('value')
@kdclick.pass_obj
def set(obj, key, value):
    """Set config value"""
    obj.kdctl.update_config(**{key: value})
    return obj.kdctl.config


main.add_command(allowed_ports.ap)
main.add_command(domains.domains)
main.add_command(images.images)
main.add_command(ippool.ippool)
main.add_command(nodes.nodes)
main.add_command(pods.pods)
main.add_command(predefined_apps.pa)
main.add_command(pricing.pricing)
main.add_command(pstorage.pstorage)
main.add_command(system_settings.ss)
main.add_command(users.users)
