from flask import Blueprint, render_template, redirect, request, url_for, flash, current_app, jsonify
from flask.ext.login import login_user, logout_user, login_required
from . import route, noauthroute
from ..users import User

bp = Blueprint('auth', __name__)

@noauthroute(bp, '/login', methods=['GET', 'POST'])
def login():
    message = 'You are not authorized to access the resource'
    if request.authorization is not None:
        username = request.authorization.get('username', None)
        passwd = request.authorization.get('password', None)
        if username is not None and passwd is not None:
            user = User.query.filter_by(username=username).first()
            if user is not None and user.verify_password(passwd):
                login_user(user)
                return redirect(request.args.get('next'))
            message = 'Username or password invalid'
    response = jsonify({'code': 401, 'message': message})
    response.status_code = 401
    return response