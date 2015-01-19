from ..core import db

import socket
import random


class Minion(db.Model):
    __tablename__ = 'minions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ip = db.Column(db.String(40), unique=True)
    hostname = db.Column(db.String(255))
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
        kwargs.pop('status')    # because now it's computable
        super(Minion, self).__init__(**kwargs)
        ip = kwargs.get('ip')
        hostname = kwargs.get('hostname')

        # TODO implement
        self.cpu_cores = 1
        self.ram = 512*1024*1024
        self.disk = 10*1024*1024*1024

        if (not ip) and (not hostname):
            raise Exception('Provide ip or hostname')

        if ip:
            if hostname:
                try:
                    h_ip = socket.gethostbyname(hostname)
                except socket.error:
                    raise Exception("Can't resolve hostname {0} to ip".format(hostname))
                if h_ip != ip:
                    raise Exception("Hostname ip doesn't match given ip")
                self.ip = ip
                self.hostname = hostname
            else:
                self.ip = ip
                self.hostname = None
        else:   # when hostname provided instead ip
            try:
                self.ip = socket.gethostbyname(hostname)
            except socket.error:
                raise Exception("Can't resolve hostname {0} to ip".format(hostname))
            self.hostname = hostname

    def __repr__(self):
        return "<Minion(ip='{0}')>".format(self.ip)