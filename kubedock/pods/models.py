from sqlalchemy.dialects import postgresql
from ..core import db

class Pod(db.Model):
    __tablename__ = 'pods'
    
    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    name = db.Column(db.String(length=255), unique=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    kubes = db.Column(db.Integer, nullable=False, default=1)
    config = db.Column(postgresql.JSON)
    status = db.Column(db.String(length=32), default='unknown')
    states = db.relationship('PodStates', backref='pod')
    
    def __repr__(self):
        return "<Pod(id='%s', name='%s', owner_id='%s', config='%s', status='%s')>" % (
            self.id, self.name, self.owner_id, self.config, self.status)


class PodStates(db.Model):
    __tablename__ = 'pod_states'
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'), primary_key=True, nullable=False)
    start_time = db.Column(db.Integer, primary_key=True, nullable=False)
    end_time = db.Column(db.Integer, nullable=True)
    
    def __repr__(self):
        return "<Pod(pod_id='%s', start_time='%s', end_time='%s')>" % (
            self.pod_id, self.start_time, self.end_time)

class ImageCache(db.Model):
    __tablename__ = 'image_cache'
    
    query = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return "<ImageCache(query='%s', data='%s', time_stamp='%s'')>" % (
            self.query, self.data, self.time_stamp)


class DockerfileCache(db.Model):
    __tablename__ = 'dockerfile_cache'
    
    image = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return "<DockerfileCache(image='%s', data='%s', time_stamp='%s'')>" % (
            self.image, self.data, self.time_stamp)
