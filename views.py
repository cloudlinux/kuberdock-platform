from flask import g, redirect, url_for, request, flash, render_template
from flask.views import MethodView
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import exc
from config import DATABASE_URL
from models import User, Container
from forms import RegisterUserForm


engine = create_engine(DATABASE_URL)
Session = sessionmaker(engine)
session = Session()


class Index(MethodView):
    def get(self):
        q = session.query(User)
        return render_template('index.html', users=q.all())

class RegisterUserView(MethodView):
    def get(self):
        form = RegisterUserForm(request.form)
        return render_template('register.html', form=form)

    def post(self):
        form = RegisterUserForm(request.form)
        if form.validate():
            user = User(form.login.data, form.email.data,
                     form.fullname.data, form.password.data)
            try:
                session.rollback()
                session.add(user)
                session.commit()
                flash('Thanks for registering')
                return redirect(url_for('index'))
            except exc.IntegrityError:
                g.alert_type = 'danger'
                flash('"{0}" already registered'.format(form.email.data))
                # return render_template('register.html', form=form)
        return render_template('register.html', form=form)