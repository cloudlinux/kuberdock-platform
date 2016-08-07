from .. import kdclick

from ..kdclick.access import ADMIN, USER


@kdclick.group(help='Commands for pods management.',
               available_for=(ADMIN, USER))
def pods():
    pass


###############################################################################
# ADMIN
###############################################################################
@pods.command(available_for=ADMIN)
@kdclick.option('--owner')
@kdclick.pass_obj
def list(obj, **params):
    return obj.kdctl.pods.list(**params)


@pods.command(available_for=ADMIN)
@kdclick.argument('pod-id')
@kdclick.option('--owner')
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.pods.get(**params)


@pods.command(available_for=ADMIN)
@kdclick.data_argument('pod-data')
@kdclick.option('--owner')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.pods.create(**params)


@pods.command(available_for=ADMIN)
@kdclick.argument('pod-id')
@kdclick.data_argument('pod-data')
# todo: uncomment in api/v2
# @kdclick.option('--owner')  # should be added in api/v2
@kdclick.pass_obj
def update(obj, **params):
    return obj.kdctl.pods.update(**params)


@pods.command(available_for=ADMIN)
@kdclick.argument('pod-id')
@kdclick.option('--owner')
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.pods.delete(**params)


###############################################################################
# USER
###############################################################################
@pods.command(available_for=USER)
@kdclick.pass_obj
def list(obj, **params):
    return obj.kdctl.pods.list(**params)


@pods.command(available_for=USER)
@kdclick.argument('pod-id')
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.pods.get(**params)


@pods.command(available_for=USER)
@kdclick.data_argument('pod-data')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.pods.create(**params)


@pods.command(available_for=USER)
@kdclick.argument('pod-id')
@kdclick.data_argument('pod-data')
# todo: uncomment in api/v2
# @kdclick.option('--owner')  # should be added in api/v2
@kdclick.pass_obj
def update(obj, **params):
    return obj.kdctl.pods.update(**params)


@pods.command(available_for=USER)
@kdclick.argument('pod-id')
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.pods.delete(**params)
