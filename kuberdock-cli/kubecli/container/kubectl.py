from ..helper import make_config
from .container import KubeCtl

def parser(subs):
    resource_help = "A resource name to take action upon"
    kubectl = subs.add_parser('kubectl')
    kubectl.set_defaults(call=wrapper)
    action = kubectl.add_subparsers(
        help="Action",
        title="Target actions",
        description="Valid actions for targets",
        dest="action")

    get = action.add_parser('get')
    get_resource = get.add_subparsers(
        help="Resource",
        title="Target resource",
        description="Valid resources for targets",
        dest="resource")
    get_pod = get_resource.add_parser('pod')
    get_pods = get_resource.add_parser('pods')
    get_pod.add_argument('name', nargs='?', help=resource_help)
    get_pods.add_argument('name', nargs='?', help=resource_help)

    desc = action.add_parser('describe')
    desc_resource = desc.add_subparsers(
        help="Resource",
        title="Target resource",
        description="Valid resources for targets",
        dest="resource")
    desc_pod = desc_resource.add_parser('pod')
    desc_pods = desc_resource.add_parser('pods')
    desc_pod.add_argument('name', help=resource_help)
    desc_pods.add_argument('name', help=resource_help)


    delete = action.add_parser('delete')
    delete_resource = delete.add_subparsers(
        help="Resource",
        title="Target resource",
        description="Valid resources for targets",
        dest="resource")
    delete_pod = delete_resource.add_parser('pod')
    delete_pods = delete_resource.add_parser('pods')
    delete_pod.add_argument('name', help=resource_help)
    delete_pods.add_argument('name', help=resource_help)

def wrapper(data):
    args = make_config(data)
    container = KubeCtl(**args)
    getattr(container, args.get('action', 'get'), 'get')()