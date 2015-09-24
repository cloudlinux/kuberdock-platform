from kubedock.billing.models import Package, PackageKube
from kubedock.core import db


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Remove deprecated packages...')
    try:
        Package.query.filter_by(id=0, name='basic').update(
            {Package.name: 'Standard package'})  # rename
        for id_, name in ((1, 'professional'), (2, 'enterprise')):  # remove
            package = Package.query.filter_by(id=id_, name=name).first()
            if package is not None and not package.users:
                PackageKube.query.filter_by(package_id=id_).delete()
                db.session.delete(package)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Recreate deprecated packages...')
    try:
        Package.query.filter_by(id=0).update({Package.name: 'basic'})

        add = db.session.add
        for id_, name, deposit, kubes in ((1, 'professional', 1, ((0, 0), (1, 1))),
                                          (2, 'enterprise', 2, ((0, 0), (1, 1), (2, 2)))):
            if Package.query.get(id_) is None:
                add(Package(id=id_, name=name, first_deposit=deposit,
                            currency='USD', period='hour', prefix='$', suffix=' USD'))
                for kube_id, kube_price in kubes:
                    add(PackageKube(package_id=id_, kube_id=kube_id, kube_price=kube_price))

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
