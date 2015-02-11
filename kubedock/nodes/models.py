from ..core import db
import random


class Node(db.Model):
    __tablename__ = 'nodes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ip = db.Column(db.String(40), unique=True)
    hostname = db.Column(db.String(255), unique=True)
    cpu_cores = db.Column(db.Integer, nullable=False)
    ram = db.Column(db.BigInteger, nullable=False)
    disk = db.Column(db.BigInteger, nullable=False)  # all? free? visible to docker?

    @property
    def labels(self):
        return {
            'tier': random.choice(['frontend', 'backend']),
            'environment': random.choice(['production', 'qa', 'dev']),
        }

    @labels.setter
    def labels(self, val):
        pass    # TODO implement writing to kubernetes

    @property
    def annotations(self):
        return {
            'description': 'Some additional data, even in binary or json. About Software Env and others',
            'sw_version': random.choice(['v1.4', 'v1.4', 'v1.4', 'v1.4', 'v1.4', 'v1.4', 'v1.4', 'v1.3']),
        }

    @annotations.setter
    def annotations(self, val):
        pass    # TODO implement writing to kubernetes

    def __init__(self, **kwargs):
        super(Node, self).__init__(**kwargs)

        # TODO implement
        self.cpu_cores = 1
        self.ram = 512*1024*1024
        self.disk = 10*1024*1024*1024

    def __repr__(self):
        return "<Node(hostname='{0}', ip='{1}')>".format(self.hostname, self.ip)