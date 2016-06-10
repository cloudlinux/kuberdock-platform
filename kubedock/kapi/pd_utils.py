"""Some utilities for persistent drives.
"""
import os
from collections import namedtuple

from ..settings import (
    PD_SEPARATOR_USERNAME, PD_SEPARATOR_USERID, PD_NAMESPACE, PD_NS_SEPARATOR,
    CEPH, AWS)

ParsedPDName = namedtuple('ParsedPDName', ('drive', 'uid', 'uname'))


def compose_pdname(drive, user):
    """
    Creates persistent drive name with user identifier.

    :param drive: persistent disk name
    :param user: User object or user id
    """
    user_id = getattr(user, 'id', user)
    is_localstorage_backend = not (CEPH or AWS)
    if is_localstorage_backend:
        drivename = os.path.join(str(user_id), drive)
    else:
        drivename = PD_SEPARATOR_USERID.join((drive, str(user_id)))
    if PD_NAMESPACE and (CEPH or AWS):
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
