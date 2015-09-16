import ipaddress
from datetime import datetime
from sqlalchemy.dialects import postgresql
from ..core import db
from ..models_mixin import BaseModelMixin
from ..settings import PD_SEPARATOR
from ..users.models import User


def to_timestamp(dt):
    return int((dt - datetime(1970, 1, 1)).total_seconds())


class ContainerState(db.Model):
    __tablename__ = 'container_states'
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'),
                       primary_key=True, nullable=False)
    container_name = db.Column(db.String(length=255), primary_key=True,
                               nullable=False)
    docker_id = db.Column(db.String(length=80), primary_key=True,
                          nullable=False, server_default='unknown')
    kubes = db.Column(db.Integer, primary_key=True, nullable=False, default=1)
    start_time = db.Column(db.DateTime, primary_key=True, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    user = db.relationship('Pod', backref='states')

    def __repr__(self):
        return ("<ContainerState(pod_id={}, container_name={}, "
                "docker_id={}, kubes={}, start_time={}, "
                "end_time={})>".format(
                    self.pod_id, self.container_name,
                    self.docker_id, self.kubes, self.start_time,
                    self.end_time))


class IpState(BaseModelMixin, db.Model):
    __tablename__ = 'ip_states'
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'),
                       primary_key=True, nullable=False)
    ip_address = db.Column(db.BigInteger, nullable=False)
    start_time = db.Column(db.DateTime, primary_key=True, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    pod = db.relationship('Pod')
    user = db.relationship('User', secondary='pods', backref='ip_states')

    def __repr__(self):
        return ("<IpState(pod_id='{0}', ip_address='{1}', start='{2}', end='{3}')>"
                .format(self.pod_id, self.ip_address, self.start_time, self.end_time))

    @classmethod
    def start(cls, pod_id, ip_address):
        cls.end(pod_id, ip_address)  # just to make sure
        cls(pod_id=pod_id, ip_address=ip_address, start_time=datetime.utcnow()).save()

    @classmethod
    def end(cls, pod_id, ip_address):
        cls.query.filter_by(pod_id=pod_id, ip_address=ip_address, end_time=None)\
            .update({'end_time': datetime.utcnow()})
        db.session.commit()

    def to_dict(self):
        return {'pod_id': self.pod_id,
                'ip_address': str(ipaddress.ip_address(self.ip_address)),
                'start': to_timestamp(self.start_time),
                'end': to_timestamp(datetime.utcnow() if self.end_time is None else
                                    self.end_time)}


class PersistentDiskState(BaseModelMixin, db.Model):
    __tablename__ = 'pd_states'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pd_name = db.Column(db.String, nullable=False)
    size = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, primary_key=True, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref='pd_states')

    def __repr__(self):
        return ("<PersistentDiskState(user_id='{0}', pd_name='{1}', start='{2}', end='{3}')>"
                .format(self.user_id, self.pd_name, self.start_time, self.end_time))

    @classmethod
    def start(cls, user_id, pd_name, size):
        cls.end(user_id, pd_name)  # just to make sure
        cls(user_id=user_id, pd_name=pd_name,
            start_time=datetime.utcnow(), size=size).save()

    @classmethod
    def end(cls, user_id=None, pd_name=None, sys_drive_name=None):
        query = cls.query.filter_by(end_time=None)
        if user_id is None or pd_name is None:
            pd_name, username = sys_drive_name.rsplit(PD_SEPARATOR, 1)
            query = query.filter_by(pd_name=pd_name).join(User).filter(
                User.username == username)
        else:
            query = query.filter_by(pd_name=pd_name, user_id=user_id)
        query.update({'end_time': datetime.utcnow()})
        db.session.commit()

    def to_dict(self, exclude=()):
        data = {'user_id': self.user_id, 'pd_name': self.pd_name, 'size': self.size,
                'start': to_timestamp(self.start_time),
                'end': to_timestamp(datetime.utcnow() if self.end_time is None else
                                    self.end_time)}
        for field in exclude:
            data.pop(field, None)
        return data
