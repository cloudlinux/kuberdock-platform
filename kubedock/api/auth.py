from flask import Blueprint, current_app, request, jsonify, session
from uuid import uuid4

from ..exceptions import APIError, PermissionDenied, NotAuthorized
from ..users import User
#from ..users.signals import user_logged_in
from ..login import auth_required, login_user, current_user
from ..sessions import create_token
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


@auth.route('/token2', methods=['POST'])
def token2():
    username = request.json.get('username')
    password = request.json.get('password')
    if username is None or password is None:
        raise NotAuthorized
    user = User.query.filter_by(username=username).first()
    if user is None or user.deleted:
        raise NotAuthorized
    if not user.active:
        raise PermissionDenied
    if not user.verify_password(password):
        raise NotAuthorized
    if session.sid is None:
        session.sid = str(uuid4())
    login_user(user)
    token = create_token(session)

    return jsonify({
        'status': 'OK',
        'id': session.sid,
        'token': token})


@auth.route('/logout', methods=['GET'])
@auth_required
def logout():
    current_app.logger.debug(vars(current_user))
    pass