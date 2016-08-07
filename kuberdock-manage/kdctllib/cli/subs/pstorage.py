from .. import kdclick

from ..kdclick.access import ADMIN, USER


@kdclick.group(help='Commands for persistent volumes management.',
               available_for=(ADMIN, USER))
def pstorage():
    pass


###############################################################################
# ADMIN
###############################################################################
@pstorage.command(available_for=ADMIN)
@kdclick.option('--owner')
@kdclick.pass_obj
def list(obj, **params):
    return obj.kdctl.pstorage.list(**params)


@pstorage.command(available_for=ADMIN)
@kdclick.argument('device-id')
@kdclick.option('--owner')
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.pstorage.get(**params)


@pstorage.command(available_for=ADMIN)
@kdclick.data_argument('device-data')
@kdclick.option('--owner')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.pstorage.create(**params)


@pstorage.command(available_for=ADMIN)
@kdclick.argument('device-id')
@kdclick.option('--owner')
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.pstorage.delete(**params)


###############################################################################
# USER
###############################################################################
@pstorage.command(available_for=USER)
@kdclick.pass_obj
def list(obj, **params):
    return obj.kdctl.pstorage.list(**params)


@pstorage.command(available_for=USER)
@kdclick.argument('device-id')
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.pstorage.get(**params)


@pstorage.command(available_for=USER)
@kdclick.data_argument('device-data')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.pstorage.create(**params)


@pstorage.command(available_for=USER)
@kdclick.argument('device-id')
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.pstorage.delete(**params)
