import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
import datetime


Base = declarative_base()


class User(Base):

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, nullable=False)
    login = Column(String(16))
    fullname = Column(String(64))
    password = Column(String(64))
    email = Column(String(64), unique=True, nullable=False)
    created = Column(TIMESTAMP)

    def __init__(self, login, email, fullname, password):
        self.login = login
        self.email = email
        self.fullname = fullname
        self.password = generate_password_hash(password)
        self.created = datetime.datetime.now()

    def __repr__(self):
        return '<User %r>' % self.login

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Container(Base):

    __tablename__ = 'containers'

    id = Column(Integer, primary_key=True, nullable=False)
    cnt_uuid = Column(String(36), unique=True)
    name = Column(String(128))
    desc = Column(String(128))
    docker_id = Column(String(256))
    docker_tag = Column(String(128))
    deployment_type = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', backref=backref('container', order_by=id))
    copies = Column(Integer)
    size = Column(Integer)
    command = Column(String(512))
    crash_recovery = Column(Integer)
    auto_destroy = Column(Integer)
    deployment_strategy = Column(Integer)
    # entrypoint = Column(String(256))
    # subdomain = Column(String(512)) # I am not sure what it really means
    state = Column(Integer) # 0 - new,
                            # 1 - starting, 2 - running,
                            # 3 - stopping, 4 - stopped
                            # 4 - terminating, 5 - terminated,
                            # 6 - redeploy
    started = Column(TIMESTAMP, nullable=True)
    stopped = Column(TIMESTAMP, nullable=True)
    terminated = Column(TIMESTAMP, nullable=True)

    def __init__(self, *a, **kw):
        self.cnt_uuid = str(uuid.uuid4())
        self.name = kw.get('name')
        self.docker_id = kw.get('docker_id')
        self.docker_tag = kw.get('docker_tag')
        self.desc = kw.get('desc')
        self.deployment_type = kw.get('deployment_type')
        self.copies = kw.get('copies')
        self.size = kw.get('size')
        self.command = '/usr/bin/start_cnt.sh'
        self.crash_recovery = kw.get('crash_recovery')
        self.auto_destroy = kw.get('auto_destroy')
        self.deployment_strategy = kw.get('deployment_strategy')
        self.user_id = kw.get('user_id')
        self.state = 0

    def __repr__(self):
        return '<Container %r>' % self.name


# class ContainerPort(Base):
#     __tablename__ = 'container_ports'
#     container_id = Column(Integer, ForeignKey('container.id'))
#     port = Column(Integer)
#     protocol = Column(Integer) # 0 - tcp, 1 udp

#     container = relationship('Container', backref=backref('port', order_by=port))

# class ContainerEnvVar(Base):
#     __tablename_ = 'container_env_vars'
#     container_id = Column(Integer, ForeignKey('containers.id'))
#     name = Column(String(256))
#     value = Column(String(4096))

#     container = relationship('Container', backref=backref('env_var', order_by=name))


# class ContainerLink(Base):
#     __tablename__ = 'container_links'
#     id_from = Column(Integer, ForeignKey('containers.id'))
#     id_to = Column(Integer, ForeignKey('containers.id'))
