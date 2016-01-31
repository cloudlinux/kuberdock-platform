"""Some utilities for persistent drives.
"""
from collections import namedtuple

from ..settings import (
    PD_SEPARATOR_USERNAME, PD_SEPARATOR_USERID, PD_NAMESPACE, PD_NS_SEPARATOR)
from ..users.models import User


ParsedPDName = namedtuple('ParsedPDName', ('drive', 'uid', 'uname'))

def parse_pd_name(pdname):
    """Extracts user and drive name from composite persistent drive name.
    :return: ParsedPDName tuple or None in case of unknown pdname format.
    """
    drive = uid = uname = None
    try:
        drive, uid = pdname.rsplit(PD_SEPARATOR_USERID)
        uid = int(uid)
    except (ValueError, TypeError):
        try:
            drive, uname = pdname.rsplit(PD_SEPARATOR_USERNAME)
        except ValueError:
            return None
    return ParsedPDName(drive, uid, uname)


def get_drive_and_user(pdname):
    """Extracts drive name and user from persistent drive name.
    :return: tuple of drive name and User object
    """
    parsed = parse_pd_name(pdname)
    if not parsed:
        return (None, None)
    if parsed.uid is not None:
        user = User.query.filter(User.id == parsed.uid).first()
    elif parsed.uname is not None:
        user = User.query.filter(User.username == parsed.uname).first()
    else:
        return (parsed.drive, None)
    return (parsed.drive, user)


def compose_pdname(drive, user):
    """
    Creates persistent drive name with user identifier.

    :param drive: persistent disk name
    :param user: User object or user id
    """
    user_id = getattr(user, 'id', user)
    drivename = PD_SEPARATOR_USERID.join((drive, str(user_id)))
    if PD_NAMESPACE:
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
