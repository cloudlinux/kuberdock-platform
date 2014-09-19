#!/usr/bin/env python2
from flask import Flask
from flask.ext.admin import Admin
from flask.ext.admin.contrib.sqla import ModelView
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from views import UserAdminView, ContainerAdminView
from models import User, Container


app = Flask(__name__)
app.config['SECRET_KEY'] = '123456790'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(engine)
session = Session()


admin = Admin(app, name='Container Admin')

admin.add_view(ModelView(User, session))
admin.add_view(ModelView(Container, session))

admin.add_view(ContainerAdminView(category='Add'))
admin.add_view(UserAdminView(category='Add'))
