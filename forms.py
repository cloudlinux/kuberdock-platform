from wtforms import BooleanField, StringField, IntegerField, TextAreaField, RadioField, validators
from flask_wtf import Form


class RegisterUserForm(Form):
    login =     StringField('Login', [validators.Length(min=4, max=16)])
    fullname =  StringField('Fullname', [validators.Length(min=4, max=64)])
    password =  StringField('Password', [validators.Length(min=4, max=64)])
    email =     StringField('Email Address', [validators.Length(min=6, max=64)])

class LoginUserForm(Form):
    email =     StringField('Email Address', [validators.Length(min=6, max=64)])
    password =  StringField('Password', [validators.Length(min=4, max=64)])

class AddContainerForm(Form):
    name =                 StringField('Name', [validators.Length(min=4, max=128)])
    docker_id =            StringField('Image', [validators.Length(min=4, max=64)])
    docker_tag =           StringField('Image Tag', [validators.Length(min=4, max=64)])
    desc =                 TextAreaField('Description', [validators.Length(min=4, max=64)])
    deployment_type =      RadioField('Deployment Type', choices=[('0', 'Single Container'), ('1', 'Container Cluster')])
    copies =               IntegerField('Copies', [validators.NumberRange(min=0, max=10)])
    size =                 RadioField('Size', choices=[('XS','XS'), ('S','S'), ('M','M'), ('L','L'), ('XL','XL')])
    crash_recovery =       IntegerField('Crash Recovery', [validators.NumberRange(min=0, max=1)])
    auto_destroy =         IntegerField('Auto Destroy', [validators.NumberRange(min=0, max=1)])
    deployment_strategy =  IntegerField('Deployment Strategy', [validators.NumberRange(min=0, max=1)])
