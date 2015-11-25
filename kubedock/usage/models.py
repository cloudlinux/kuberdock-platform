import ipaddress
from datetime import datetime
from sqlalchemy.dialects import postgresql
from flask import current_app
from ..core import db
from ..models_mixin import BaseModelMixin
from ..kapi import pd_utils


def to_timestamp(dt):
    return int((dt - datetime(1970, 1, 1)).total_seconds())


class ContainerState(BaseModelMixin, db.Model):
    __tablename__ = 'container_states'
    pod_state_id = db.Column(db.ForeignKey('pod_states.id'), nullable=False)
    container_name = db.Column(db.String(length=255), primary_key=True,
                               nullable=False)
    docker_id = db.Column(db.String(length=80), primary_key=True,
                          nullable=False, server_default='unknown')
    kubes = db.Column(db.Integer, primary_key=True, nullable=False, default=1)
    start_time = db.Column(db.DateTime, primary_key=True, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    exit_code = db.Column(db.Integer, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    pod = db.relationship('Pod', secondary='pod_states', uselist=False,
                          backref='container_states', viewonly=True)
    pod_state = db.relationship('PodState', backref='container_states')

    def __repr__(self):
        data = {field: getattr(self, field) for field in self.__table__.c.keys()}
        return '<ContainerState({0})>'.format(
            ', '.join('{0}={1}'.format(*item) for item in data.iteritems()))

    def fix_overlap(self, end_time):
        """Shift end_time timestamp of container state to fix overlaping."""
        current_app.logger.warn('Overlaping ContainerStates was found: {0} at {1}.'
                                .format(self.container_name, self.start_time,
                                        self.end_time, end_time))
        self.end_time = end_time
        if self.exit_code is None and self.reason is None:
            self.exit_code = 1
            self.reason = 'Reason of failure was missed.'

    @classmethod
    def in_range(cls, start=None, end=None):
        """Get query matching container states that lie in specified time range.
        """
        query = cls.query.order_by(cls.start_time.desc())
        if end is not None:
            query = query.filter(cls.start_time < end)
        if start is not None:
            query = query.filter(cls.end_time.is_(None) | (cls.end_time > start))
        return query


class PodState(BaseModelMixin, db.Model):
    __tablename__ = 'pod_states'
    __table_args__ = (db.Index('ix_pod_id_start_time',
                               'pod_id', 'start_time', unique=True),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    last_event_time = db.Column(db.DateTime, nullable=True)
    last_event = db.Column(db.String(255), nullable=True)
    hostname = db.Column(db.String(255), nullable=True)
    pod = db.relationship('Pod', backref='states')

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
    user = db.relationship('User', secondary='pods', backref='ip_states',
                           viewonly=True, uselist=False)

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
