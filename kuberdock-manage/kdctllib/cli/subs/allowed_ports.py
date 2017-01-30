
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

from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand


@kdclick.group('allowed-ports', available_for=ADMIN)
@kdclick.pass_obj
def ap(obj):
    """Commands for allowed ports management"""
    obj.executor = obj.kdctl.allowed_ports


@ap.command()
@kdclick.pass_obj
class List(SimpleCommand):
    """Get list of opened ports"""
    pass


@ap.command()
@kdclick.argument('port', type=int)
@kdclick.argument('protocol', default='tcp')
@kdclick.pass_obj
class Open(SimpleCommand):
    """Open port"""
    pass


@ap.command()
@kdclick.argument('port', type=int)
@kdclick.argument('protocol', default='tcp')
@kdclick.pass_obj
class Close(SimpleCommand):
    """Close port"""
    pass
