import ipaddress
from datetime import datetime
from sqlalchemy.dialects import postgresql
from ..core import db
from ..models_mixin import BaseModelMixin
from ..kapi import pd_utils


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
    pod = db.relationship('Pod', backref='states')

    def __repr__(self):
        return ("<ContainerState(pod_id={}, container_name={}, "
                "docker_id={}, kubes={}, start_time={}, "
                "end_time={})>".format(
                    self.pod_id, self.container_name,
                    self.docker_id, self.kubes, self.start_time,
                    self.end_time))


class PodState(db.Model):
    __tablename__ = 'pod_states'
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'),
                       primary_key=True, nullable=False)
    start_time = db.Column(db.DateTime, primary_key=True, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    last_event_time = db.Column(db.DateTime, nullable=True)
    last_event = db.Column(db.String(255), nullable=True)
    hostname = db.Column(db.String(255), nullable=True)

    @classmethod
    def save_state(cls, pod_id, event, hostname):
        """Creates new or updates existing one pod state entity.
        If existing pod entities are closed and/or belongs to another host name,
        then will be created new state. If there is one not closed state for
        the same pod_id and host, then it will be updated.
        Returns created or updated PodState entity.

        """
        entity = cls.get_alive_state(pod_id, hostname)
        current_time = datetime.utcnow()
        if entity is None:
            entity = cls(
                pod_id=pod_id,
                start_time=current_time,
                end_time=None,
                hostname=hostname
            )
            db.session.add(entity)
        entity.last_event = event
        entity.last_event_time = current_time
        if event == 'DELETED':
            entity.end_time = current_time
        try:
            db.session.commit()
        except:
            db.session.rollback()
            raise
        if entity.end_time is None:
            cls.close_other_pod_states(pod_id, entity.start_time, hostname)
        return entity

    @classmethod
    def get_alive_state(cls, pod_id, hostname):
        """Returns existing PodState entity which is not closed and belongs
        to the given host name. If there is no such item, then will return None.

        """
        entity = cls.query.filter(
            cls.pod_id == pod_id,
            cls.end_time == None,
            cls.hostname == hostname
        ).order_by(cls.start_time.desc()).first()
        return entity

    @classmethod
    def close_other_pod_states(cls, pod_id, start_time, hostname):
        """Closes all not closed PodState with the given pod_id, which belongs
        to another host names. Or those which belongs to the same host name
        and have start_time less then given (for some reasons it may occurs,
        though it's incorrect situation).

        """
        current_time = datetime.utcnow()
        cls.query.filter(
            cls.pod_id == pod_id,
            cls.end_time == None,
            db.or_(
                cls.hostname != hostname,
                db.and_(
                    cls.hostname == hostname,
                    cls.start_time < start_time
                )
            )
        ).update({
            cls.end_time: current_time
        })
        try:
            db.session.commit()
        except:
            db.session.rollback()
            raise

    def to_dict(self):
        return {
            'pod_id': self.pod_id,
            'hostname': self.hostname,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'last_event': self.last_event,
            'last_event_time': self.last_event_time
        }


class IpState(BaseModelMixin, db.Model):
    __tablename__ = 'ip_states'
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'),
                       primary_key=True, nullable=False)
    ip_address = db.Column(db.BigInteger, nullable=False)
    start_time = db.Column(db.DateTime, primary_key=True, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    pod = db.relationship('Pod')
    user = db.relationship('User', secondary='pods', backref='ip_states', viewonly=True)

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
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
            pd_name, user = pd_utils.get_drive_and_user(sys_drive_name)
            if not user:
                return
            query = query.filter_by(pd_name=pd_name, user_id=user.id)
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
