from ..core import db


class Node(db.Model):
    __tablename__ = 'nodes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ip = db.Column(db.String(40), unique=True)
    hostname = db.Column(db.String(255), unique=True)
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    state = db.Column(db.String(40))

    def __repr__(self):
        return "<Node(hostname='{0}', ip='{1}', kube_type='{2} ({3})')>".format(
            self.hostname, self.ip, self.kube.id, self.kube.name)