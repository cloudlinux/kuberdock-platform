from flask import Blueprint, request, jsonify
from flask.ext.login import login_user
from . import APIError
from ..users import User
from ..users.signals import user_logged_in

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.authorization is not None:
        username = request.authorization.get('username', None)
        passwd = request.authorization.get('password', None)
        if username is not None and passwd is not None:
            user = User.query.filter_by(username=username).first()
            if not user.active:
                raise APIError("User '{0}' is blocked".format(username), 403)
            elif user is not None and user.verify_password(passwd):
                login_user(user)
                user_logged_in.send(user.id)
                return jsonify({'status': 'OK',
                                'next': request.args.get('next')})
            raise APIError('Username or password invalid', 401)
    raise APIError('You are not authorized to access the resource', 401)