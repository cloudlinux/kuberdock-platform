from functools import wraps

from flask import jsonify

from .updates.helpers import get_maintenance
from .utils import APIError, get_user_role



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
