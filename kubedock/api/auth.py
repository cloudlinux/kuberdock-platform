from flask import Blueprint, current_app, jsonify, request, session

from ..exceptions import APIError, NotAuthorized, PermissionDenied
from ..login import auth_required, current_user, login_user
from ..sessions import create_token
from ..users.models import User, load_user_by_token

auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/token', methods=['GET'])
def token():
    if request.authorization is not None:
        username = request.authorization.get('username', None)
        passwd = request.authorization.get('password', None)
        if username is not None and passwd is not None:
            user = User.query.filter(User.username_iequal(username)).first()
            if user is None or user.deleted:
                pass
            elif not user.active:
                raise APIError("User '{0}' is blocked".format(username), 403)
            elif user.verify_password(passwd):
                return jsonify({'status': 'OK', 'token': user.get_token()})
            raise APIError('Username or password invalid', 401)
    raise APIError('You are not authorized to access the resource', 401)


@auth.route('/token2', methods=['POST'])
def token2():
    username = request.json and request.json.get('username')
    password = request.json and request.json.get('password')
    token = (request.json and request.json.get('token') or
             request.args.get('token'))

    user = None
    if token:
        user = load_user_by_token(token)
    elif username is not None and password is not None:
        user = User.query.filter(User.username_iequal(username)).first()
    if user is None or user.deleted:
        raise NotAuthorized
    if not user.active:
        raise PermissionDenied
    if not token and not user.verify_password(password):
        raise NotAuthorized
    login_user(user)
    token2 = create_token(session)

    return jsonify({'status': 'OK', 'token': token2})


@auth.route('/logout', methods=['GET'])
@auth_required
def logout():
    current_app.logger.debug(vars(current_user))
    pass
