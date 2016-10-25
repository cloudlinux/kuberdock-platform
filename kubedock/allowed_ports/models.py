from sqlalchemy.schema import UniqueConstraint

from ..core import db


class AllowedPort(db.Model):
    __tablename__ = 'allowed_ports'

    id = db.Column(db.Integer, primary_key=True)
    port = db.Column(db.Integer, nullable=False)
    protocol = db.Column(db.String(12), nullable=False)

    __table_args__ = (
        UniqueConstraint(port, protocol),
    )

    def dict(self):
        return {'port': self.port, 'protocol': self.protocol}
