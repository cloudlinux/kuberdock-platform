from flask.ext.login import current_user
from .users.models import User, Role, Permission, SessionData
from .pods.models import Pod, ImageCache, DockerfileCache
from flask import abort
from functools import wraps

def permission_required(permission):
    def decorator(f):
        @wraps
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return permission_required(Permission.ADMINISTER)(f)
