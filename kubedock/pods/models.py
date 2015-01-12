from sqlalchemy.dialects import postgresql
from ..core import db

class Pod(db.Model):
    __tablename__ = 'pods'
    
    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    name = db.Column(db.String(length=255))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    config = db.Column(postgresql.JSON)
    status = db.Column(db.String(length=32), default='unknown')
    
    def __repr__(self):
        return "<Pod(id='%s', name='%s', owner_id='%s', config='%s', status='%s')>" % (
            self.id, self.name, self.owner_id, self.config, self.status)

    
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
