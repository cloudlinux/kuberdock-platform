
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

from distutils.util import strtobool

from kubedock.exceptions import APIError
from kubedock.users import User


def extbool(value):
    """Bool or string with values ('0', '1', 'true', 'false', 'yes') to bool.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, basestring):
        return bool(strtobool(value))
    raise TypeError('Invalid type. Must be bool or string')


def get_user(username):
    user = User.get(username)
    if user is None:
        raise APIError('User "{0}" does not exist'.format(username),
                       404, 'UserNotFound', {'name': username})
    return user
