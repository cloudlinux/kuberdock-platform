from flask import Blueprint, current_app, request, jsonify, abort, session
from uuid import uuid4
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from . import APIError
from ..users import User
#from ..users.signals import user_logged_in
from ..login import auth_required, login_user, current_user

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
        abort(401)
    user = User.query.filter_by(username=username).first()
    if user is None or user.deleted:
        abort(401)
    if not user.active:
        abort(403)
    if not user.verify_password(password):
        abort(401)
    login_user(user)
    if session.sid is None:
        session.sid = str(uuid4())
    secret = current_app.config.get('SECRET_KEY')
    lifetime = current_app.config.get('SESSION_LIFETIME')
    s = Serializer(secret, lifetime)
    token = s.dumps(dict(dict(session), sid=session.sid))

    return jsonify({
        'status': 'OK',
        'id': session.sid,
        'token': token.decode('ascii')})


@auth.route('/logout', methods=['GET'])
@auth_required
def logout():
    current_app.logger.debug(vars(current_user))
    pass