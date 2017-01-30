
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


@kdclick.group(available_for=ADMIN)
@kdclick.pass_obj
def ippool(obj):
    """Commands for IP pool management"""
    obj.executor = obj.kdctl.ippool


def _verify_page(ctx, param, value):
    conditions = [
        value is None or value > 0
    ]
    if not all(conditions):
        raise kdclick.BadParameter('Page must be greater than 0.')
    return value


@ippool.command()
@kdclick.option('--page', type=int, callback=_verify_page)
@kdclick.option('--free-only', is_flag=True)
@kdclick.pass_obj
class List(SimpleCommand):
    """List all existing IP pools"""
    pass


@ippool.command()
@kdclick.argument('network')
@kdclick.option('--page', type=int, callback=_verify_page)
@kdclick.pass_obj
class Get(SimpleCommand):
    """Get existing IP pool by network"""
    pass


@ippool.command()
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    """Create new IP pool"""
    pass


@ippool.command()
@kdclick.argument('network')
@kdclick.data_argument('data')
@kdclick.pass_obj
class Update(SimpleCommand):
    """Update existing IP pool"""
    pass


@ippool.command()
@kdclick.argument('network')
@kdclick.pass_obj
class Delete(SimpleCommand):
    """Delete existing IP pool"""
    pass
