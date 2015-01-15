from flask import current_app
from flask.ext.login import UserMixin
from sqlalchemy.dialects import postgresql
from werkzeug.security import generate_password_hash, check_password_hash
from ..core import db, login_manager
import datetime

@login_manager.user_loader
def load_users(user_id):
    return db.session.query(User).get(int(user_id))


class Permission:
    USE = 0x01
    RESELL = 0x02
    ADMINISTER = 0x80


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=False)
    description = db.Column(db.Text, nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    pods = db.relationship('Pod', backref='owner', lazy='dynamic')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['FLASKY_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def can(self, permissions):
        return self.role is not None and (self.role.permissions & permissions) == permissions
    
    def is_administrator(self):
        return self.can(Permission.ADMINISTER)
    
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    rolename = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')
    
    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.USE, True),
            'Reseller': (Permission.USE | Permission.RESELL, False),
            'Administrator': (0xff, False)}
        for r in roles:
            role = Role.query.filter_by(rolename=r).first()
            if role is None:
                role = Role(rolename=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()


class SessionData(db.Model):
    __tablename__ = 'session_data'
    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    data = db.Column(db.PickleType, nullable=True)
    time_stamp = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, id, data=None):
        self.id = id
        self.data = data
        self.time_stamp = datetime.datetime.now()
        
    def __repr__(self):
        return "<SessionData(session_id='%s', data='%s', time_stamp='%s'')>" % (
            self.session_id, self.data, self.time_stamp)
