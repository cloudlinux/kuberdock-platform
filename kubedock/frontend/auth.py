from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask.ext.login import login_user, logout_user, current_user

from ..users import User
from ..users.signals import user_logged_in, user_logged_out


auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    username = request.form.get('login-form-username-field')
    passwd = request.form.get('login-form-password-field')
    if username is not None and passwd is not None:
        user = User.query.filter_by(username=username).first()
        error = 'Invalid credentials provided'
        if user and not user.active:
            return render_template('errors/user_inactive.html'), 403
        elif user is not None and user.verify_password(passwd):
            login_user(user)
            user_logged_in.send(user.id)
            return redirect(request.args.get('next') or url_for('main.index'))
        flash(error, 'error')
    return render_template('auth/login.html')


@auth.route('/logout')
def logout():
    user_logged_out.send(current_user.id)
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('main.index'))