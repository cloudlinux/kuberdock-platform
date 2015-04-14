from ..helper import make_config
from .container import Container

def parser(subs):
    container = subs.add_parser('container')
    container.set_defaults(call=wrapper)
    action = container.add_subparsers(help="Action", title="Target actions", description="Valid actions for targets", dest="action")

    c_set = action.add_parser('set')
    c_set.add_argument('name', help="Container name")
    
    c_set.add_argument('-i', '--image', help="Image to take action upon")
    c_set.add_argument('-d', '--delete', help="Delete image from a container")
    c_set.add_argument('--port-index', default=0, type=int, help="Index of ports entry (by default 0)")
    c_set.add_argument('--container-port', type=int, help="Add or change a container port of ports entry")
    c_set.add_argument('--host-port', type=int, help="Add or change a host port of ports entry")
    c_set.add_argument('--protocol', choices=['tcp', 'udp'], help="Change protocol of ports entry (by default 'tcp')")
    c_set.add_argument('--volume-name', help="Set name for shareable volume")
    c_set.add_argument('--mount-path', help="Point to existent mount path entry or create a new one", dest="mountPath")
    c_set.add_argument('--read-only', help="Set mount path entry read-only", dest="readOnly")
    c_set.add_argument('--kubes', help="Set image kubes")
    c_set.add_argument('--kube-type', help="Set container kube type")
    c_set.add_argument('--service', action="store_true", help="Create an entrypoint for the container")
    c_set.add_argument('--cluster', action="store_true", help="Create containers cluster")
    c_set.add_argument('--replicas', type=int, default=1, help="Set number of replicas in cluster. By default 1")
    c_set.add_argument('--public', action="store_true", help="Assign a public IP address to container", dest="set_public_ip")
    c_set.add_argument('--restart-policy', default="always", help="Set container restart policy", dest="restartPolicy")
    c_set.add_argument('--run', action="store_true", help="Send this container data to KuberDock to run")
    c_set.add_argument('--save-only', action="store_true", help="Send this container data to KuberDock to save")
    
    c_del = action.add_parser('delete')
    c_del.add_argument('name', help="Container name")
    
    c_start = action.add_parser('start')
    c_start.add_argument('name', help="Container name")

    c_stop = action.add_parser('stop')
    c_stop.add_argument('name', help="Container name")

    c_list = action.add_parser('list')
    c_list.add_argument('--pending', action="store_true", help="List not submitted containers only")

    c_show = action.add_parser('show')
    c_show.add_argument('name', help="Container name")


def wrapper(data):
    args = make_config(data)
    print args