from functools import wraps

from flask import current_app, g, jsonify, request
from flask.ext.login import current_user

from .exceptions import APIError, PermissionDenied, NotAuthorized
from .updates.helpers import get_maintenance
from .users import User
from .utils import get_user_role


def login_required_or_basic_or_token(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_app.login_manager._login_disabled:
            return func(*args, **kwargs)
        if not current_user.is_authenticated():
            authenticated_user = None
            if request.authorization is not None:
                username = request.authorization.get('username', None)
                passwd = request.authorization.get('password', None)
                if username is not None and passwd is not None:
                    user = User.query.filter_by(username=username).first()
                    if user is not None and user.verify_password(passwd):
                        authenticated_user = user
            else:
                token = request.args.get('token')
                if token:
                    authenticated_user = User.query.filter_by(
                        token=token).first()

            if authenticated_user is None or authenticated_user.deleted:
                raise NotAuthorized()
            if not authenticated_user.active:
                raise PermissionDenied('User is in inactive status')
            g.user = authenticated_user
        return func(*args, **kwargs)
    return decorated_view


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
