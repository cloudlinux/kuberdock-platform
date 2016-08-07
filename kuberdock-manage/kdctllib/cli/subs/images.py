from .. import kdclick

from ..kdclick.access import ADMIN, USER


@kdclick.group(help='Commands for docker images management.',
               available_for=(ADMIN, USER))
def images():
    pass


@images.command()
@kdclick.argument('search-key')
@kdclick.option('-p', '--page', type=int, help='Page to display')
@kdclick.option('-R', '--REGISTRY', type=int,
                help='Registry to search in. By default dockerhub is used')
@kdclick.pass_obj
def search(obj, **params):
    return obj.kdctl.images.search(**params)
