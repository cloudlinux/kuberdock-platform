from flask import redirect, url_for, request, flash
from flask.ext.admin import BaseView, expose
from wtforms_alchemy import ModelForm
from models import User, Container


class UserForm(ModelForm):
    class Meta:
        model = User

class ContainerForm(ModelForm):
    class Meta:
        model = Container



class ContainerAdminView(BaseView):
    @expose('/')
    def index(self):
        form = ContainerForm(request.form)
        return self.render('default.html', form=form)


class UserAdminView(BaseView):
    @expose('/')
    def index(self):
        form = UserForm(request.form)
        return self.render('default.html', form=form)

    @expose('/test/')
    def test(self):
        return self.render('default.html')
