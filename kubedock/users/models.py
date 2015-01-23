from flask.ext.login import UserMixin
from sqlalchemy.dialects import postgresql
from werkzeug.security import generate_password_hash, check_password_hash
from ..core import db, login_manager
import datetime


@login_manager.user_loader
def load_users(user_id):
    return db.session.query(User).get(int(user_id))


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
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_administrator(self):     # TODO remove this, prefer normal permission check
        if self.role.rolename == 'SuperAdmin':
            return True
        else:
            return False

    def __repr__(self):
        return "<User(username='{0}', email='{1}')>".format(self.username, self.email)
    

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    rolename = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')
    
    def __repr__(self):
        return "<Role(rolename='{0}')>".format(self.rolename)


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
        return "<SessionData(session_id='%s', data='%s', time_stamp='%s')>" % (
            self.session_id, self.data, self.time_stamp)
