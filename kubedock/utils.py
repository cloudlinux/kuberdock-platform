#import pkgutil
#import importlib

from flask import current_app, request, jsonify, g
from flask.ext.login import current_user
from functools import wraps

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
            response = jsonify({'code': 403,'message': 'Access denied'})
            response.status_code = 403
            return response
            #return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view

def check_perms(rolename):
    roles = ['User', 'Administrator']
    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            role = g.user.role.rolename
            if rolename not in roles or roles.index(role) < roles.index(rolename):
                response = jsonify({'code': 403,'message': 'Access denied'})
                response.status_code = 403
                return response
            return func(*args, **kwargs)
        return decorated_view
    return wrapper

#from flask import Blueprint
#from flask.json import JSONEncoder as NativeJSONEncoder
#
#def register_blueprints(app, package_name, package_path):
#    rv = []
#    for _, name, _ in pkgutil.iter_modules(package_path):
#        m = importlib.import_module('%s.%s' % (package_name, name))
#        for item in dir(m):
#            item = getattr(m, item)
#            if isinstance(item, Blueprint):
#                app.register_blueprint(item)
#            rv.append(item)
#    return rv
#
#class JSONEncoder(NativeJSONEncoder):
#    def default(self, obj):
#        if isinstance(obj, JsonSerializer):
#            return obj.to_json()
#        return super(JSONEncoder, self).default(obj)
#    
#class JsonSerializer(object):
#    __json_public__ = None
#    __json_hidden__ = None
#    __json_modifiers__ = None
#
#    def get_field_names(self):
#        for p in self.__mapper__.iterate_properties:
#            yield p.key
#
#    def to_json(self):
#        field_names = self.get_field_names()
#
#        public = self.__json_public__ or field_names
#        hidden = self.__json_hidden__ or []
#        modifiers = self.__json_modifiers__ or dict()
#
#        rv = dict()
#        for key in public:
#            rv[key] = getattr(self, key)
#        for key, modifier in modifiers.items():
#            value = getattr(self, key)
#            rv[key] = modifier(value, self)
#        for key in hidden:
#            rv.pop(key, None)
#        return rv
#
#
def update_dict(src, diff):
    for key, value in diff.iteritems():
        if type(value) is dict and key in src:
            update_dict(src[key], value)
        else:
            src[key] = value
