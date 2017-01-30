
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
from ..kdclick.access import ADMIN, USER
from ..utils import (SimpleCommand, SimpleCommandWithIdNameArgs,
                     SimpleCommandWithIdNameOwnerArgs)


@kdclick.group(available_for=(ADMIN, USER))
@kdclick.pass_obj
def pstorage(obj):
    """Commands for persistent volumes management"""
    obj.executor = obj.kdctl.pstorage


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required persistent volume')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


###############################################################################
# ADMIN
###############################################################################
@pstorage.command(available_for=ADMIN)
@kdclick.option('--owner')
@kdclick.pass_obj
class List(SimpleCommand):
    """List existing persistent volumes"""
    pass


@pstorage.command(available_for=ADMIN)
@id_decorator
@kdclick.option('--owner')
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameOwnerArgs):
    """Get existing persistent volume"""
    pass


@pstorage.command(available_for=ADMIN)
@kdclick.data_argument('data')
@kdclick.option('--owner')
@kdclick.pass_obj
class Create(SimpleCommand):
    """Create new persistent volume"""
    pass


@pstorage.command(available_for=ADMIN)
@id_decorator
@kdclick.option('--owner')
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameOwnerArgs):
    """Delete existing persistent volume"""
    pass


###############################################################################
# USER
###############################################################################
@pstorage.command(available_for=USER)
@kdclick.pass_obj
class List(SimpleCommand):
    """List existing persistent volumes"""
    pass


@pstorage.command(available_for=USER)
@id_decorator
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    """Get existing persistent volume"""
    pass


@pstorage.command(available_for=USER)
@kdclick.data_argument('data')
@kdclick.pass_obj
class Create(SimpleCommand):
    """Create new persistent volume"""
    pass


@pstorage.command(available_for=USER)
@id_decorator
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameArgs):
    """Delete existing persistent volume"""
    pass
