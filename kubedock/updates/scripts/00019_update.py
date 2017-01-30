
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

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
