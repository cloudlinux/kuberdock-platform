from flask import g, redirect, url_for, request, flash, render_template, abort, session
from flask.views import MethodView
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, exc
from config import DATABASE_URL
from models import User, Container
from forms import RegisterUserForm, LoginUserForm, AddContainerForm


engine = create_engine(DATABASE_URL)
Session = sessionmaker(engine)
db_session = Session()

def add_or_none(obj):
    try:
        db_session.add(obj)
        db_session.commit()
        return True
    except:
        db_session.rollback()
    finally:
        db_session.close()
    return False


class IndexView(MethodView):
    def get(self):
        if session.get('user_id', None):
            user = db_session.query(User).get(session['user_id'])
            return render_template('user.html', user=user)
        else:
            return render_template('index.html')

class UserListView(MethodView):
    def get(self):
        users = db_session.query(User)
        return render_template('user_list.html', users=users)

class LoginUserView(MethodView):
    def get(self):
        form = LoginUserForm(request.form)
        return render_template('login.html', form=form)

    def post(self):
        form = LoginUserForm(request.form)
        if form.validate():
            user_id = session.get('user_id', None)
            if not user_id:
                try:
                    user = db_session.query(User).filter_by(email=request.form['email']).one()
                    flash('Welcome back, ' + user.fullname)
                    session['user_id'] = user.id
                    session['login'] = user.login
                    return redirect(url_for('user', user_id=user.id))
                except exc.NoResultFound:
                    g.alert_type = 'danger'
                    flash('User not found')
        return render_template('login.html', form=form)

class LogoutUserView(MethodView):
    def get(self):
        user = session.get('user_id', None)
        if user:
            flash('Logout success!')
            for k in ['user_id', 'login']: session.pop(k, None)
        return redirect(url_for('index'))

class RegisterUserView(MethodView):
    def get(self):
        form = RegisterUserForm(request.form)
        return render_template('register.html', form=form)

    def post(self):
        form = RegisterUserForm(request.form)
        if form.validate():
            user = User(form.login.data, form.email.data,
                        form.fullname.data, form.password.data)
            if add_or_none(user):
                flash('Thanks for registering')
                return redirect(url_for('user', user_id=session['user_id']))
            else:
                g.alert_type = 'danger'
                flash('"{0}" already registered'.format(form.email.data))
        return render_template('register.html', form=form)

class UserView(MethodView):
    def get(self, user_id):
        user = db_session.query(User).get(user_id)
        if not user: abort(404)
        if session.get('user_id', None) is not user_id: abort(403)
        return render_template('user.html', user=user)

class AddContainerView(MethodView):
    def get(self):
        form = AddContainerForm(request.form)
        return render_template('add_container.html', form=form)

    def post(self):
        form = AddContainerForm(request.form)
        if form.validate():
            # for i in form.__dict__.keys():
            #     if i[0] != '_' and i not in ['meta', 'SECRET_KEY', 'csrf_enabled']: print(i, form[i].data)
            user_id = session.get('user_id', None)
            if user_id:
                container = Container(
                    name=form.name.data,
                    docker_id=form.docker_id.data,
                    docker_tag=form.docker_tag.data,
                    desc=form.desc.data,
                    deployment_type=form.deployment_type.data,
                    copies=form.copies.data,
                    size=form.size.data,
                    crash_recovery=form.crash_recovery.data,
                    auto_destroy=form.auto_destroy.data,
                    deployment_strategy=form.deployment_strategy.data,
                    user_id=user_id
                    )
                if add_or_none(container):
                    return redirect(url_for('user', user_id=user_id))
            else:
                g.alert_type = 'danger'
                flash('Authorized users only!')
        return render_template('add_container.html', form=form)
