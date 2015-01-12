from flask import Blueprint, render_template, redirect, request, url_for, flash, current_app
from flask.ext.login import login_user, logout_user, login_required
from . import route, noauthroute
from ..users import User

bp = Blueprint('auth', __name__)

@noauthroute(bp, '/login', methods=['GET', 'POST'])
def login():
    username = request.form.get('login-form-username-field')
    passwd = request.form.get('login-form-password-field')
    if username is not None and passwd is not None:
        user = User.query.filter_by(username=username).first()
        if user is not None and user.verify_password(passwd):
            login_user(user)
            return redirect(request.args.get('next') or url_for('main.index'))
        flash('Invalid credentials provided', 'error')
    return render_template('auth/login.html')

@route(bp, '/logout')
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('main.index'))