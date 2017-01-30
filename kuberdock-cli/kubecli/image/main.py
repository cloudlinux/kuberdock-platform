
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
