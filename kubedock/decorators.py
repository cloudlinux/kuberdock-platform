
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

from flask import jsonify

from .exceptions import APIError
from .login import get_user_role
from .updates.helpers import get_maintenance


def maintenance_protected(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if get_maintenance():
            raise APIError(
                "Sorry, Kuberdock now is in maintenance mode, please, "
                "wait until it finishes upgrade and try again")
        return func(*args, **kwargs)
    return wrapped


def check_perms(rolename):
    roles = ['User', 'Administrator']

    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            role = get_user_role()
            if rolename not in roles or \
                    roles.index(role) < roles.index(rolename):
                response = jsonify({'code': 403, 'message': 'Access denied'})
                response.status_code = 403
                return response
            return func(*args, **kwargs)
        return decorated_view
    return wrapper
