from ..core import db
from ..utils import UPDATE_STATUSES


class Node(db.Model):
    __tablename__ = 'nodes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ip = db.Column(db.String(40), unique=True)
    hostname = db.Column(db.String(255), unique=True)
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    state = db.Column(db.String(40))
    upgrade_status = db.Column(db.Text, default=UPDATE_STATUSES.applied)

    def __repr__(self):
        return "<Node(hostname='{0}', ip='{1}', kube_type='{2} ({3})')>".format(
            self.hostname, self.ip, self.kube.id, self.kube.name)


class NodeMissedAction(db.Model):
    __tablename__ = 'node_missed_actions'
    host = db.Column(db.String(255), primary_key=True, nullable=False)
    command = db.Column(db.Text, nullable=False)
    time_stamp = db.Column(db.DateTime, primary_key=True, nullable=False)

    def __repr__(self):
        return "<NodeMissedAction(host='{0}', command='{1}', time_stamp='{2}')>".format(
            self.host, self.command, self.time_stamp)
