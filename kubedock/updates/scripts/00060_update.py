from kubedock.billing.models import Kube
from kubedock.core import db

OLD_NAME = "Standard kube"
NEW_NAME = "Standard"


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Rename `Standard kube` to `Standard`')
    kube = db.session.query(Kube).filter(Kube.name == OLD_NAME).first()
    if kube:
        kube.name = NEW_NAME
        db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    upd.print_log('Rename `Standard` to `Standard kube` back')
    kube = db.session.query(Kube).filter(Kube.name == NEW_NAME).first()
    if kube:
        kube.name = OLD_NAME
        db.session.commit()
