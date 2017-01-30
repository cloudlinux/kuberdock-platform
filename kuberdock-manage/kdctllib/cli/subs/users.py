
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

from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group(available_for=ADMIN)
@kdclick.pass_obj
def users(obj):
    """Commands for users management"""
    obj.executor = obj.kdctl.users


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required user')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


class _UsersCommandWithIdNameArgs(SimpleCommandWithIdNameArgs):
    name_field = 'username'


@users.command()
@kdclick.option('--short', is_flag=True)
@kdclick.option('--with-deleted', is_flag=True)
@kdclick.pass_obj
class List(SimpleCommand):
    """List existing users"""
    pass


@users.command()
@id_decorator
@kdclick.option('--short', is_flag=True)
@kdclick.option('--with-deleted', is_flag=True)
@kdclick.pass_obj
class Get(_UsersCommandWithIdNameArgs):
    """Get existing user"""
    pass


@users.command()
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    """Create new user"""
    pass


@users.command()
@id_decorator
@kdclick.data_argument('data')
@kdclick.pass_obj
class Update(_UsersCommandWithIdNameArgs):
    """Update existing user"""
    pass


@users.command()
@id_decorator
@kdclick.option('--force', is_flag=True)
@kdclick.pass_obj
class Delete(_UsersCommandWithIdNameArgs):
    """Delete existing user"""
    pass
