from flask import Blueprint, request, jsonify
from flask.ext.login import login_user

from ..exceptions import APIError
from ..users import User
from ..users.signals import user_logged_in

auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/token', methods=['GET'])
def token():
    if request.authorization is not None:
        username = request.authorization.get('username', None)
        passwd = request.authorization.get('password', None)
        if username is not None and passwd is not None:
            user = User.query.filter_by(username=username).first()
            if user is None or user.deleted:
                pass
            elif not user.active:
                raise APIError("User '{0}' is blocked".format(username), 403)
            elif user.verify_password(passwd):
                return jsonify({'status': 'OK', 'token': user.get_token()})
            raise APIError('Username or password invalid', 401)
    raise APIError('You are not authorized to access the resource', 401)
