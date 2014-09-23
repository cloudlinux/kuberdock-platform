#!/usr/bin/env python2
from flask import Flask
from views import IndexView, UserView, RegisterUserView
from models import User, Container


app = Flask(__name__)
app.config['SECRET_KEY'] = '123456790'


@app.template_filter('date')
def _jinja2_filter_datetime(date, fmt=None):
    if fmt:
        return date.strftime(fmt)
    else:
        return date.strftime('%d-%m-%Y')


app.add_url_rule('/', view_func=IndexView.as_view('index'))
app.add_url_rule('/register', view_func=RegisterUserView.as_view('register'))
app.add_url_rule('/user/<int:user_id>', view_func=UserView.as_view('user'))
app.add_url_rule('/user/list', view_func=IndexView.as_view('user_list'))
