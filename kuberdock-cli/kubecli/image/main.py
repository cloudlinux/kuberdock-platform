from .image import Image
from ..helper import make_config


def parser(subs):
    image = subs.add_parser('image')
    image.set_defaults(call=wrapper)
    action = image.add_subparsers(help="Action",
                                  title="Target actions",
                                  description="Valid actions for targets",
                                  dest="action")

    search = action.add_parser('search')
    search.add_argument('search_string', help="Search string")
    search.add_argument('-p', '--page', default=0, type=int,
                        help="Page to display")
    search.add_argument('-R', '--registry',
                        help="Registry to search in. "
                             "By default dockerhub is used")

    get = action.add_parser('get')
    get.add_argument('image', help="Image name")


def wrapper(data):
    args = make_config(data)
    container = Image(**args)
    getattr(container, args.get('action', 'get'), 'get')()
