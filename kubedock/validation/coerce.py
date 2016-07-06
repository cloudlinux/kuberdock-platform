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
