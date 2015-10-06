from sqlalchemy import or_


def upgrade(upd, with_testing, *args, **kwargs):
    from kubedock.billing.models import PackageKube
    upd.print_log('Remove damaged PackageKubes...')

    PackageKube.query.filter(or_(PackageKube.package_id.is_(None),
                                 PackageKube.kube_id.is_(None))).delete()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
