#!/usr/bin/env python

import argparse
import ConfigParser

from kubecli.container import main as container
from kubecli.image import main as image


def parse_config(path):
    data = {}
    conf = ConfigParser.ConfigParser()
    conf.optionxform = str
    configs = conf.read(path)
    if len(configs) == 0:   # no configs found
        return data
    for section in conf.sections():
        data.update(dict(conf.items(section)))
    return data


def process_args(args):
    excludes = ['func', 'config']
    config = parse_config(args.config)
    args_dict = {k: v for k, v in vars(args).items() if k not in excludes}
    for k in args_dict:
        if args_dict[k] is not None:
            config[k] = args_dict[k]
    return config


def parse_args():
    parser = argparse.ArgumentParser("KuberDock command line utilities")
    parser.add_argument('-c', '--config', default='/etc/kubecli.conf')
    parser.add_argument('-u', '--user', help="User account to use. By default current one is used")
    parser.add_argument('-p', '--password')
    subs = parser.add_subparsers(help="Commands", title="Commands", description="Valid commands", dest="commands")
    
    # container module. Handles all container related activities
    containers = subs.add_parser('container')
    containers.set_defaults(call=container)
    action = containers.add_subparsers(help="Action", title="Command actions", description="Valid actions for commands", dest="action")
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

    images = subs.add_parser('image')
    images.set_defaults(call=image)
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    data = process_args(args)
    args.call(**data)