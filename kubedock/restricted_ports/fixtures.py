from kubedock.core import db
from .models import RestrictedPort


RESTRICTED_PORTS = [
    (25, 'tcp')
]


def add_restricted_ports():
    for port, protocol in RESTRICTED_PORTS:
        if RestrictedPort.query.filter_by(port=port, protocol=protocol).first():
            continue
        restricted_port = RestrictedPort(port=port, protocol=protocol)
        db.session.add(restricted_port)
    db.session.commit()


if __name__ == '__main__':
    add_restricted_ports()
