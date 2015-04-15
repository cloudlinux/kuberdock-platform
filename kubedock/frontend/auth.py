from flask import (
    Blueprint, render_template, redirect, request, url_for, flash, session)
from flask.ext.login import login_user, logout_user, current_user

from ..users import User
from ..users.signals import user_logged_in, user_logged_out


auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated():
        return redirect(url_for('main.index'))
    username = request.form.get('login-form-username-field')
    passwd = request.form.get('login-form-password-field')
    if username is not None and passwd is not None:
        user = User.query.filter_by(username=username).first()
        error = 'Invalid credentials provided'
        if user is None:
            pass
        elif not user.active:
            return render_template('errors/user_inactive.html'), 403
        elif user.verify_password(passwd):
            login_user(user)
            user_logged_in.send(user.id)
            main_index = url_for('main.index')
            next_ = request.args.get('next') or main_index
            if user.is_administrator() and next_ == main_index:
                return redirect(url_for('nodes.index'))
            return redirect(next_)
        flash(error, 'error')
    return render_template('auth/login.html')


@auth.route('/logout')
def logout():
    user_logged_out.send(current_user.id)
    logout_user()
    session.pop('auth_by_another', None)
    flash('You have been logged out')
    return redirect(url_for('main.index'))
