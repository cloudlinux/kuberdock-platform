#import pkgutil
#import importlib

from flask import current_app, request, jsonify, g
from flask.ext.login import current_user
from functools import wraps

from .settings import KUBE_MASTER_URL
from .users import User


def login_required_or_basic(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_app.login_manager._login_disabled:
            return func(*args, **kwargs)
        if not current_user.is_authenticated():
            if request.authorization is not None:
                username = request.authorization.get('username', None)
                passwd = request.authorization.get('password', None)
                if username is not None and passwd is not None:
                    user = User.query.filter_by(username=username).first()
                    if user is not None and user.verify_password(passwd):
                        g.user = user
                        return func(*args, **kwargs)
            raise APIError('Not Authorized', status_code=401)
            #return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


def check_perms(rolename):
    roles = ['User', 'Administrator']

    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            role = get_user_role()
            if rolename not in roles or roles.index(role) < roles.index(rolename):
                response = jsonify({'code': 403, 'message': 'Access denied'})
                response.status_code = 403
                return response
            return func(*args, **kwargs)
        return decorated_view
    return wrapper


def update_dict(src, diff):
    for key, value in diff.iteritems():
        if type(value) is dict and key in src:
            update_dict(src[key], value)
        else:
            src[key] = value


def get_api_url(*args, **kwargs):
    url = kwargs.get('url') or KUBE_MASTER_URL
    return '{0}/{1}'.format(url, '/'.join([str(arg) for arg in args]))


# separate function because set_roles_loader decorator don't return function. Lib bug.
def get_user_role():
    print current_user.role
    try:
        return current_user.role.name
    except AttributeError:
        try:
            return g.user.role.name
        except AttributeError:
            return 'AnonymousUser'


class APIError(Exception):
    def __init__(self, message, status_code=400):
        if isinstance(message, (list, tuple, dict)):
            message = str(message)
        self.message = message
        self.status_code = status_code
