from ..helper import make_config
from .image import Image

def parser(subs):
    docker = subs.add_parser('docker')
    docker.set_defaults(call=wrapper)
    action = docker.add_subparsers(help="Action",
                                    title="Target actions",
                                    description="Valid actions for targets",
                                    dest="action")
    
    search = action.add_parser('search')
    ps = action.add_parser('ps')
    search.add_argument('search_string', help="Search string")
    search.add_argument('-p', '--page', default=0, type=int, help="Page to display")
    search.add_argument('-R', '--registry', help="Registry to search in. By default dockerhub is used")
    
    ps = action.add_parser('ps')
    ps.add_argument('name', help="Name to show contents")

def wrapper(data):
    args = make_config(data)
    container = Image(**args)
    getattr(container, args.get('action', 'get'), 'get')()