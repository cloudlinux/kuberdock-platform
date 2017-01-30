
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

"""Some utilities for persistent drives.
"""
import os
from collections import namedtuple

from ..settings import (
    PD_SEPARATOR_USERNAME, PD_SEPARATOR_USERID, PD_NAMESPACE, PD_NS_SEPARATOR,
    CEPH)

ParsedPDName = namedtuple('ParsedPDName', ('drive', 'uid', 'uname'))


def compose_pdname(drive, user):
    """
    Creates persistent drive name with user identifier.

    :param drive: persistent disk name
    :param user: User object or user id
    """
    user_id = getattr(user, 'id', user)
    # Note that AWS backend also works as localstorage
    is_localstorage_backend = not CEPH
    if is_localstorage_backend:
        drivename = os.path.join(str(user_id), drive)
    else:
        drivename = PD_SEPARATOR_USERID.join((drive, str(user_id)))
    if PD_NAMESPACE and CEPH:
        # do not use namespace for localstorage backend
        return PD_NS_SEPARATOR.join([
            PD_NAMESPACE, drivename
        ])
    return drivename


def compose_pdname_legacy(drive, user):
    """Creates persistent drive name with user name. This function is only
    for some backward compatibility issues, now username is replaced with
    user identifier for PD names.
    """
    return PD_SEPARATOR_USERNAME.join((drive, str(user.username)))
