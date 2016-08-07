from .. import kdclick

from ..kdclick.access import ADMIN, USER


@kdclick.group('system-settings',
               help='Commands for system settings management.',
               available_for=(ADMIN, USER))
def ss():
    pass


@ss.command(available_for=(ADMIN, USER))
@kdclick.pass_obj
def list(obj):
    return obj.kdctl.system_settings.list()


@ss.command(available_for=(ADMIN, USER))
@kdclick.argument('sid')
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.system_settings.get(**params)


@ss.command(available_for=ADMIN)
@kdclick.argument('sid')
@kdclick.argument('value')
@kdclick.pass_obj
def update(obj, **params):
    return obj.kdctl.system_settings.update(**params)
