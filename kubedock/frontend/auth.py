from flask import (
    Blueprint, render_template, redirect, request, url_for, flash, session)
from flask.ext.login import login_user, logout_user
from flask.ext.login import current_user, login_required
from sqlalchemy.sql import not_

from ..users import User
from ..users.signals import user_logged_in, user_logged_out
from ..core import login_manager


auth = Blueprint('auth', __name__)


@login_manager.request_loader
def load_users_from_request(request):
    token = request.args.get('token', '')
    if 'token' in request.form:
        token = request.form['token']
    if token:
        username = token.split('|', 1)[0] or None
        user = User.filter(
            User.username == username, User.active, not_(User.deleted)).first()
        if user and user.verify_token(token):
            login_user(user)
            user_logged_in.send((user.id, request.remote_addr))
            return user


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated():
        return redirect(url_for('main.index'))
    username = request.form.get('login-form-username-field')
    passwd = request.form.get('login-form-password-field')
    token = request.args.get('token')
    if token:
        username = token.split('|', 1)[0] or None
    if username is not None and (passwd is not None or token is not None):
        user = User.query.filter_by(username=username).first()
        error = 'Invalid credentials provided'
        if user is None or user.deleted:
            pass
        elif not user.active:
            error = 'User "{0}" is blocked'.format(username)
        elif passwd is not None and user.verify_password(passwd) or user.verify_token(token):
            login_user(user)
            user_logged_in.send((user.id, request.remote_addr))
            main_index = url_for('main.index')
            next_ = request.args.get('next') or main_index
            return redirect(next_)
        flash(error, 'error')
    return render_template('auth/login.html')


@auth.route('/logout')
@login_required
def logout():
    user_logged_out.send(current_user.id)
    logout_user()
    session.pop('auth_by_another', None)
    flash('You have been logged out')
    return redirect(url_for('main.index'))
