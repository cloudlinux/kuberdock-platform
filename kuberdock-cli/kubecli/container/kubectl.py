
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import argparse

from .container import KubeCtl
from ..helper import make_config


def parser(subs):
    resource_help = "A resource name to take action upon"
    template_id_help = "Template identifier"
    name_help = "Template name"
    yaml_file_help = "YAML file path or '-' to pass file content via stdin"

    kubectl = subs.add_parser('kubectl')
    kubectl.set_defaults(call=wrapper)
    action = kubectl.add_subparsers(
        help="Action",
        title="Target actions",
        description="Valid actions for targets",
        dest="action")

    action.add_parser('register')

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
    get_template = get_resource.add_parser(
        'template', help='Read template for predefined application'
    )
    get_template.add_argument(
        '--id', required=True, help=template_id_help, type=int
    )
    get_templates = get_resource.add_parser(
        'templates', help='Read all templates for predefined applications'
    )
    get_templates.add_argument(
        '--page', required=False, help='Page number'
    )
    get_templates.add_argument(
        '-o', '--origin', required=False,
        help='Filter out received templates by origin'
    )

    desc = action.add_parser('describe')
    desc_resource = desc.add_subparsers(
        help="Resource",
        title="Target resource",
        description="Valid resources for targets",
        dest="resource")
    desc_pod = desc_resource.add_parser('pod')
    desc_pods = desc_resource.add_parser('pods')
    desc_pod.add_argument('name', help=resource_help)
    desc_pods.add_argument('name', help=resource_help, nargs='?')

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
    delete_template = delete_resource.add_parser(
        'template', help='Delete template of predefined application'
    )
    delete_template.add_argument(
        '--id', required=True,
        help=template_id_help
    )

    create = action.add_parser('create')
    # At the moment we accept only commands for creating of user's pods
    # from YAML specs.
    # Also there will be needed a command to create "predefined apps",
    # so here we require to explicitly defined target. It allows us to add
    # new targets without breaking user's pods creation.
    create_resource = create.add_subparsers(
        help="Resource",
        title="Target resource",
        description="Valid resources for targets",
        dest="resource")
    create_pod = create_resource.add_parser(
        'pod', help="Create and run user's pod from yaml file"
    )
    create_pod.add_argument(
        '-f', '--filename',
        type=argparse.FileType('r'),
        required=True,
        help="YAML file path or '-' to pass file content via stdin")
    create_template = create_resource.add_parser(
        'template',
        help="Create and run predefined application template from yaml file"
    )
    create_template.add_argument(
        '-f', '--filename',
        type=argparse.FileType('r'),
        required=True,
        help=yaml_file_help
    )
    create_template.add_argument(
        '-n', '--name',
        required=True,
        help=name_help
    )

    create_template.add_argument(
        '-o', '--origin',
        default='unknown',
        help="Sets origin for determining the app visibility scope"
    )

    update = action.add_parser('update')
    update_resource = update.add_subparsers(
        help="Resource",
        title="Target resource",
        description="Valid resources for targets",
        dest="resource")
    update_template = update_resource.add_parser(
        'template', help="Update exsiting template with new content from yaml"
    )
    update_template.add_argument(
        '--id', required=True,
        help=template_id_help
    )
    update_template.add_argument(
        '-f', '--filename',
        type=argparse.FileType('r'),
        required=False,
        help=yaml_file_help
    )
    update_template.add_argument(
        '-n', '--name',
        required=False,
        help=name_help
    )

    post = action.add_parser('postprocess')
    post.add_argument('name', help="Container name")
    post.add_argument('--uid', help="User UID to be run for")


def wrapper(data):
    args = make_config(data)
    container = KubeCtl(**args)
    getattr(container, args.get('action', 'get'), 'get')()
